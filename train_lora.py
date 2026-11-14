"""Run on a dedicated CUDA host, never imported by the desktop server."""
import argparse,json,pathlib

def main():
    p=argparse.ArgumentParser();p.add_argument('--model',required=True);p.add_argument('--data',required=True);p.add_argument('--output',required=True);p.add_argument('--qlora',action='store_true');p.add_argument('--steps',type=int,default=100);p.add_argument('--max-length',type=int,default=1024);a=p.parse_args()
    import torch
    from transformers import AutoModelForCausalLM,AutoTokenizer,BitsAndBytesConfig,Trainer,TrainingArguments,DataCollatorForSeq2Seq
    from peft import LoraConfig,get_peft_model,prepare_model_for_kbit_training
    from datasets import Dataset
    if not torch.cuda.is_available():raise RuntimeError('A dedicated CUDA GPU is required')
    train=pathlib.Path(a.data)/'train.jsonl';test=pathlib.Path(a.data)/'test.jsonl'
    def read(path):return [json.loads(line)['messages'] for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    train_rows=read(train);test_rows=read(test)
    if len(train_rows)<10 or len(test_rows)<2:raise ValueError('Need at least 10 reviewed training and 2 held-out test samples')
    tokenizer=AutoTokenizer.from_pretrained(a.model)
    if tokenizer.pad_token is None:tokenizer.pad_token=tokenizer.eos_token
    kwargs={'device_map':{'':0},'torch_dtype':torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16}
    if a.qlora:kwargs['quantization_config']=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',bnb_4bit_use_double_quant=True,bnb_4bit_compute_dtype=kwargs['torch_dtype'])
    model=AutoModelForCausalLM.from_pretrained(a.model,**kwargs)
    if a.qlora:model=prepare_model_for_kbit_training(model)
    model=get_peft_model(model,LoraConfig(r=8,lora_alpha=16,lora_dropout=.05,target_modules=['q_proj','k_proj','v_proj','o_proj'],task_type='CAUSAL_LM'))
    model.config.use_cache=False
    def encode(messages):
        full=tokenizer.apply_chat_template(messages,tokenize=True,add_generation_prompt=False,enable_thinking=False)
        prefix=tokenizer.apply_chat_template(messages[:-1],tokenize=True,add_generation_prompt=True,enable_thinking=False)
        ids=full[:a.max_length];labels=[-100]*min(len(prefix),len(ids))+ids[min(len(prefix),len(ids)):]
        return {'input_ids':ids,'attention_mask':[1]*len(ids),'labels':labels}
    def dataset(rows):
        values=[encode(m) for m in rows];values=[v for v in values if any(i!=-100 for i in v['labels'])]
        if not values:raise ValueError('All assistant tokens truncated; shorten prompts')
        return Dataset.from_list(values)
    args=TrainingArguments(output_dir=a.output,max_steps=a.steps,per_device_train_batch_size=1,per_device_eval_batch_size=1,gradient_accumulation_steps=8,learning_rate=1e-4,logging_steps=5,save_steps=50,save_total_limit=2,report_to=[],gradient_checkpointing=True,bf16=torch.cuda.is_bf16_supported(),fp16=not torch.cuda.is_bf16_supported())
    trainer=Trainer(model=model,args=args,train_dataset=dataset(train_rows),eval_dataset=dataset(test_rows),data_collator=DataCollatorForSeq2Seq(tokenizer,padding=True,label_pad_token_id=-100))
    before=trainer.evaluate();trainer.train();after=trainer.evaluate()
    model.save_pretrained(a.output);tokenizer.save_pretrained(a.output)
    (pathlib.Path(a.output)/'evaluation.json').write_text(json.dumps({'before':before,'after':after,'auto_deployed':False},indent=2))
    print('Adapter saved. Validate task accuracy independently before deployment.')

if __name__=='__main__':main()
