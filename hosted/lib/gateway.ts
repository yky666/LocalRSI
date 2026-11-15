import { env } from 'cloudflare:workers';

const readPaths = /^\/api\/(status|capabilities|notes|knowledge|files|tasks\/[a-f0-9]{32})$/;
const writePaths = /^\/api\/(tasks|resume|cancel|upload|index|search|feedback|notes|notes\/delete|approve|export-training|evolve\/(create|evaluate|activate|rollback))$/;
const json = (value: unknown, status = 200) => Response.json(value, {status, headers:{'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}});
const db = () => { if (!env.DB) throw new Error('Storage unavailable'); return env.DB; };
function same(a: string, b: string) { let d=a.length^b.length; for(let i=0;i<Math.max(a.length,b.length);i++) d|=(a.charCodeAt(i)||0)^(b.charCodeAt(i)||0);return d===0; }
async function body(request: Request) {
  const text=await request.text();
  if(new TextEncoder().encode(text).length>8*1024*1024)throw new Error('Request exceeds 8MB');
  return JSON.parse(text);
}
export async function gateway(request: Request): Promise<Response> {
  try {
    const url=new URL(request.url), path=url.pathname, now=Date.now();
    const database=db();
    if(path==='/relay/claim' || path==='/relay/result' || path==='/relay/heartbeat' || path==='/relay/health') {
      const key=(env as any).BRIDGE_KEY;
      if(request.method!=='POST'||!key||!same(request.headers.get('X-LocalRSI-Bridge')||'',key))return json({error:'Unauthorized worker'},401);
      const data=await body(request);
      if(path==='/relay/health'){
        const worker=await database.prepare('SELECT seen FROM workers WHERE id=?').bind('primary').first<any>();
        return json({connected:!!worker&&now-worker.seen<60000,last_seen:worker?.seen??null,checked:now});
      }
      if(path==='/relay/heartbeat'){
        await database.prepare('INSERT INTO workers (id,seen) VALUES (?,?) ON CONFLICT(id) DO UPDATE SET seen=excluded.seen').bind('primary',now).run();
        return json({ok:true});
      }
      if(path==='/relay/claim') {
        await database.prepare('INSERT INTO workers (id,seen) VALUES (?,?) ON CONFLICT(id) DO UPDATE SET seen=excluded.seen').bind('primary',now).run();
        const claim=crypto.randomUUID();
        const job=await database.prepare("UPDATE requests SET status='leased',lease=?,claimed=? WHERE id=(SELECT id FROM requests WHERE status='queued' AND created>? ORDER BY created LIMIT 1) AND status='queued' RETURNING id,owner,path,method,payload,lease").bind(claim,now,now-120000).first();
        return json({job});
      }
      if(typeof data.id!=='string'||typeof data.lease!=='string'||!Number.isInteger(data.status)||data.status<200||data.status>599)return json({error:'Invalid result'},400);
      const result=JSON.stringify({status:data.status,body:data.body});
      if(result.length>8*1024*1024)return json({error:'Result too large'},413);
      const update=await database.prepare("UPDATE requests SET result=?,status='done' WHERE id=? AND lease=? AND status='leased'").bind(result,data.id,data.lease).run();
      if(!update.meta.changes){const prior=await database.prepare("SELECT status FROM requests WHERE id=? AND lease=?").bind(data.id,data.lease).first();if(prior?.status!=='done')return json({error:'Unknown lease'},409);}
      return json({ok:true});
    }
    const owner=request.headers.get('oai-authenticated-user-id');
    if(!owner)return json({error:'Sign in required'},401);
    if(request.method==='POST'&&request.headers.get('Origin')!==url.origin)return json({error:'Same-origin request required'},403);
    if(path==='/relay/identity')return json({email:request.headers.get('oai-authenticated-user-email'),scope:'personal'});
    if(path.startsWith('/relay/results/')) {
      if(request.method!=='GET')return json({error:'Method not allowed'},405);
      const job=await database.prepare('SELECT status,result,created,claimed FROM requests WHERE id=? AND owner=?').bind(path.split('/').pop(),owner).first<any>();
      if(!job)return json({error:'Not found'},404);
      if(job.status==='done')return json(JSON.parse(job.result));
      if(now-job.created>180000)return json({status:504,body:{error:'计算端响应超时。操作可能已经执行，请检查任务记录，不要重复提交写操作。'}});
      return json({pending:true},202);
    }
    if(!(request.method==='GET'&&readPaths.test(path))&&!(request.method==='POST'&&writePaths.test(path)))return json({error:'Endpoint unavailable in shared hosting'},404);
    const worker=await database.prepare('SELECT seen FROM workers WHERE id=?').bind('primary').first<any>();
    if(!worker||now-worker.seen>60000)return json({error:'计算端暂未连接，请稍后重试。'},503);
    const count=await database.prepare("SELECT count(*) AS n FROM requests WHERE owner=? AND status!='done' AND created>?").bind(owner,now-180000).first<any>();
    if(count.n>=12)return json({error:'Too many pending requests'},429);
    const payload=request.method==='POST'?await body(request):null;
    if(new TextEncoder().encode(JSON.stringify(payload)).length>1800000)return json({error:'上传内容超过网页单次传输预算，请缩短视频区间或减小附件。'},413);
    const id=crypto.randomUUID();
    await database.prepare("INSERT INTO requests (id,owner,path,method,payload,status,created) VALUES (?,?,?,?,?,'queued',?)").bind(id,owner,path,request.method,JSON.stringify(payload),now).run();
    // Results are transport records, not the durable task store. Remove old bodies.
    await database.prepare('DELETE FROM requests WHERE created<?').bind(now-86400000).run();
    return json({request_id:id},202);
  } catch(error) { return json({error:error instanceof SyntaxError?'Invalid JSON':'Request could not be processed'},400); }
}
