"""의료 접근 경로의 구성요소 및 조건부 CO2 그림. python policy_figures.py"""
import json
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from figures import setup, save, RES


def main():
    setup()
    case = json.loads((RES/'case_summary.json').read_text(encoding='utf8'))
    carbon = json.loads((RES/'carbon_summary.json').read_text(encoding='utf8'))
    fig, ax = plt.subplots(figsize=(8.2, 3.2))
    ax.set(xlim=(0, 10), ylim=(0, 4));ax.axis('off')
    def box(x, y, w, text, color):
        ax.add_patch(FancyBboxPatch((x,y),w,.62,boxstyle='round,pad=0.07',facecolor=color,edgecolor='none'))
        ax.text(x+w/2,y+.31,text,ha='center',va='center',fontsize=11,color='white')
    def arrow(x1,x2,y):ax.annotate('',(x2,y),(x1,y),arrowprops={'arrowstyle':'->','lw':1.3,'color':'#697786'})
    ax.text(0,3.68,'암사1동 주민센터 ↔ 강동성심병원: 공식 안내를 조합한 철도 경로',fontsize=11.5,weight='bold')
    for x,w,t,c in [(0,1.55,'주민센터','#476274'),(2.18,1.7,'암사역 8호선','#a83d68'),(4.48,1.8,'천호역 환승','#476274'),(6.88,1.55,'강동역 5호선','#7651a5'),(8.9,1.05,'병원','#476274')]:box(x,2.55,w,t,c)
    for a,b in [(1.62,2.08),(3.95,4.38),(6.35,6.78),(8.5,8.8)]:arrow(a,b,2.86)
    ax.text(1.87,2.2,'보행 안내\n10분',ha='center',va='top',fontsize=10)
    ax.text(5.38,2.2,'8→5호선\n참고 1분 59초',ha='center',va='top',fontsize=10)
    ax.text(8.65,2.2,'보행 안내\n5분',ha='center',va='top',fontsize=10)
    ax.text(0,1.25,'암사역 정류소 → 강동경희대병원 정류소: 3411번 환승 없는 연결',fontsize=11.5,weight='bold')
    box(0,.36,3.15,'암사역2번출구·암사종합시장\n25156 / 순번 70','#476274')
    box(6.02,.36,3.93,'강동경희대병원·명일동이마트\n25177 / 순번 82','#476274')
    arrow(3.23,5.94,.67)
    ax.text(4.58,.91,f'3411  /  {case["bus_stop_intervals"]}구간',ha='center',fontsize=10)
    ax.text(4.58,.25,'노선자료 배차 11분',ha='center',fontsize=10)
    fig.subplots_adjust(left=.02,right=.99,top=.99,bottom=.02);save(fig,'05_case_routes.png')

    fig, ax = plt.subplots(figsize=(8.2, 3.4))
    x = np.linspace(0, 400, 201)
    for km,col in [(0,'#3f7181'),(20,'#b5533d'),(40,'#8b8498')]:
        y=(x*carbon['car_co2_kg_vehicle_km_assumption']-km*carbon['bus_co2_kg_vehicle_km_assumption'])*250/1000
        ax.plot(x,y,label=f'버스 추가 {km}km/일 가정',c=col,lw=2)
    threshold=carbon['break_even_avoided_car_vehicle_km_day_for_extra_bus20']
    ax.axhline(0,c='#67717a',lw=.8);ax.axvline(threshold,c='#b5533d',lw=.9,ls='--')
    ax.scatter([threshold],[0],c='#b5533d',s=25,zorder=4)
    ax.annotate(f'추가 버스 20km/일일 때\n승용차 약 {threshold:.1f}km/일 감소가 손익분기',xy=(threshold,0),xytext=(145,-8),fontsize=10,arrowprops={'arrowstyle':'-','lw':.8,'color':'#b5533d'},color='#8a3f30')
    ax.set(xlabel='감소한 승용차 차량 주행거리 (km/일, 가정)',ylabel='연간 순감축 연료 연소 CO₂ (t, 가정)',xlim=(0,400),ylim=(-13,23))
    ax.grid(alpha=.13);ax.legend(loc='upper left',frameon=False,fontsize=9)
    ax.tick_params(labelsize=10);fig.tight_layout();save(fig,'06_carbon_conditions.png')


if __name__=='__main__':
    main()
