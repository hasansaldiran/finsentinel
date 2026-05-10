// File: src/components/EmlakEndeksiTabs.tsx
import React, { useState } from 'react'
import ChartSample from './ChartSample'
import Glossary from './Glossary'

type Tab = { id: string; title: string }

const TABS: Tab[] = [
  { id: 'genel', title: 'Genel Endeks' },
  { id: 'rapor', title: 'Raporlar' },
  { id: 'haber', title: 'Emlak Haberleri' },
  { id: 'sozluk', title: 'Emlak Sözlüğü' },
  { id: 'yorum', title: 'Kural Tabanlı Yorumlar' }
]

export default function EmlakEndeksiTabs(){
  const [active, setActive] = useState<string>('genel')

  return (
    <div style={{color:'#e6eef8',fontFamily:'Inter,monospace'}}>
      <div style={{display:'flex',gap:8,marginBottom:12}}>
        {TABS.map(t=> (
          <button key={t.id} onClick={()=>setActive(t.id)}
            style={{padding:'8px 12px',borderRadius:8,border:'none',cursor:'pointer',background: active===t.id? '#134e7c':'transparent', color: active===t.id? '#fff':'#9fb3d6'}}>
            {t.title}
          </button>
        ))}
      </div>

      <div style={{background:'#0b1220',padding:16,borderRadius:10}}>
        {active==='genel' && (
          <div>
            <h3>Genel Endeks</h3>
            <ChartSample height={260} />
          </div>
        )}
        {active==='rapor' && (
          <div>
            <h3>Raporlar</h3>
            <p style={{color:'#9fb3d6'}}>CSV indir, özet tablolar, top 10 listeler.</p>
          </div>
        )}
        {active==='haber' && (
          <div>
            <h3>Emlak Haberleri</h3>
            <ul style={{color:'#cfe8ff'}}>
              <li>Haber örneği 1</li>
              <li>Haber örneği 2</li>
            </ul>
          </div>
        )}
        {active==='sozluk' && (
          <div>
            <h3>Emlak Sözlüğü</h3>
            <Glossary />
          </div>
        )}
        {active==='yorum' && (
          <div>
            <h3>Kural Tabanlı Yorumlar</h3>
            <p style={{color:'#9fb3d6'}}>Kurallar `rules.json` ile yönetilir. Backend evaluator örneği mevcut.</p>
          </div>
        )}
      </div>
    </div>
  )
}
