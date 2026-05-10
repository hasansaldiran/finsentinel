// File: src/utils/rules-evaluator.ts
import rules from '../data/rules.json'

type Rule = {
  id:string
  when: { field:string; op:string; value:number }
  and?: { field:string; op:string; value:number }
  message:string
  kind?:string
}

function compare(op:string, a:number, b:number){
  switch(op){
    case '>': return a>b
    case '>=': return a>=b
    case '<': return a<b
    case '<=': return a<=b
    case '==': return a==b
    default: return false
  }
}

export function evaluateRules(input:any){
  const out:any[] = []
  ;(rules as Rule[]).forEach(r=>{
    const left = Number(input[r.when.field] ?? 0)
    if(!compare(r.when.op, left, Number(r.when.value))) return
    if(r.and){
      const left2 = Number(input[r.and.field] ?? 0)
      if(!compare(r.and.op, left2, Number(r.and.value))) return
    }
    // interpolate simple placeholders
    const msg = r.message.replace(/%\{(.*?)\}/g, (_,k)=> String(input[k.trim()] ?? ''))
    out.push({id:r.id, text:msg, kind:r.kind||'info'})
  })
  return out
}

export default evaluateRules
