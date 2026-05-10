// File: src/components/ChartSample.tsx
import React from 'react'
import { Line } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
} from 'chart.js'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend)

export default function ChartSample({height=240}:{height?:number}){
  const data = {
    labels: ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'],
    datasets: [
      { label: 'm² Fiyat (₺)', data: [12000,12500,13000,12800,13500,14000,14200,14100,14500,15000,15500,15800], borderColor:'#4da6ff', backgroundColor:'rgba(77,166,255,0.08)', tension:0.3 }
    ]
  }

  const opts = { responsive:true, maintainAspectRatio:false, plugins:{legend:{display:false}}, scales:{y:{ticks:{color:'#a8c7e6'}}} }

  return (
    <div style={{height}}>
      <Line data={data} options={opts as any} />
    </div>
  )
}
