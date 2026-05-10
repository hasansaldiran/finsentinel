// File: src/components/Glossary.tsx
import React, { useMemo, useState } from 'react'

const SAMPLE = [
  {term:'Arsa', category:'Arsa Türleri', def:'İmar durumuna göre kullanılabilir arazi parçası.'},
  {term:'Kat Mülkiyeti', category:'Tapu & Sicil', def:'Bağımsız bölüme ait tapu türü.'},
  {term:'Kat İrtifakı', category:'Tapu & Sicil', def:'İnşaat öncesi verilen hak.'},
  {term:'İpotek', category:'Kredi & İpotek', def:'Gayrimenkul teminatlı kredi.'},
  {term:'Kira Getirisi', category:'Kira', def:'Yıllık brüt kira getirisi (%)'},
]

export default function Glossary(){
  const [q,setQ] = useState('')
  const [cat,setCat] = useState('All')

  const cats = useMemo(()=>['All',...Array.from(new Set(SAMPLE.map(s=>s.category)))],[])
  const items = useMemo(()=> SAMPLE.filter(s=> (cat==='All' || s.category===cat) && s.term.toLowerCase().includes(q.toLowerCase())),[q,cat])

  return (
    <div>
      <div style={{display:'flex',gap:8,marginBottom:8}}>
        <input placeholder='Ara terim...' value={q} onChange={e=>setQ(e.target.value)} style={{flex:1,padding:8}} />
        <select value={cat} onChange={e=>setCat(e.target.value)} style={{padding:8}}>
          {cats.map(c=> <option key={c} value={c}>{c}</option>)}
        </select>
      </div>
      <ul>
        {items.map(i=> (
          <li key={i.term} style={{marginBottom:8}}>
            <strong>{i.term}</strong> <small style={{color:'#9fb3d6'}}>({i.category})</small>
            <div style={{color:'#cfe8ff'}}>{i.def}</div>
          </li>
        ))}
      </ul>
    </div>
  )
}
