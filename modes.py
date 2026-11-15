"""Execution policies, separate from a model's native reasoning capability."""
MODES = {
    'fast': {'tokens': 400, 'rounds': 6, 'review': False, 'instruction': '优先直接完成简单任务，减少不必要的调用。'},
    'standard': {'tokens': 700, 'rounds': 12, 'review': False, 'instruction': '复杂任务先列简短计划，执行后报告验证结果。'},
    'deep': {'tokens': 1000, 'rounds': 20, 'review': True, 'instruction': '核对约束、事实和验收标准，严格遵守用户要求的回答格式与长度。复杂操作任务执行后验证；一般知识问答直接作答。'},
}

def policy(name):
    if name not in MODES:
        raise ValueError('Unknown thinking mode')
    return MODES[name]
