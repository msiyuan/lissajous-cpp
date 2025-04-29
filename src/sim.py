import numpy as np
import matplotlib.pyplot as plt
import math
from matplotlib.colors import LogNorm

# Function to simulate Lissajous curve

def simulate_lissajous(freqx, freqy, phasex_deg, phasey_deg, image_size=512, num_points=1000000):
    
    phasex = math.radians(phasex_deg)
    phasey = math.radians(phasey_deg)
    t = np.linspace(0, 2 * np.pi, num_points)  
    X_vals = (image_size / 2) * np.sin(freqx * t + phasex) + (image_size / 2)
    Y_vals = (image_size / 2) * np.sin(freqy * t + phasey) + (image_size / 2)
    X_indices = np.floor(X_vals).astype(int)
    Y_indices = np.floor(Y_vals).astype(int)
    np.clip(X_indices, 0, image_size - 1, out=X_indices)
    np.clip(Y_indices, 0, image_size - 1, out=Y_indices)
    image = np.zeros((image_size, image_size), dtype=int)
    for x, y in zip(X_indices, Y_indices):
        image[x, y] += 1
    print(np.max(image))
    return image


def display_lissajous(image, freqx, freqy, phasex_deg, phasey_deg):
    # 创建图形对象，设置黑色背景
    plt.figure(facecolor='black')
    plt.gca().set_facecolor('black')
    
    # 使用 'viridis' 色图，它从深蓝色过渡到黄色，更容易区分
    plt.imshow(image, 
              cmap='viridis',  # 或者使用 'plasma', 'magma' 都是不错的选择
              interpolation='nearest', 
              norm=LogNorm(vmin=1, vmax=np.max(image)))

    colorbar = plt.colorbar(label='Number of Scans')
    colorbar.ax.set_ylabel('Number of Scans', color='white')
    colorbar.ax.tick_params(colors='white')

    plt.title(f'Lissajous Curve Simulation\n freqx={freqx}, freqy={freqy}, phasex_deg={phasex_deg}, phasey_deg={phasey_deg} \n fill rate: {cal_fill_rate(image):.2%}',
              color='white')
    

    plt.gca().tick_params(colors='white')

    plt.savefig(f'lissajous_curve_fx={freqx}_fy={freqy}_px_deg={phasex_deg}_py_deg={phasey_deg}.png', 
                bbox_inches='tight',
                facecolor='black',
                edgecolor='none')
    
    plt.show()

def cal_fill_rate(image):
    # import ipdb; ipdb.set_trace()
    return np.sum(image > 0) / (image.shape[0] * image.shape[1])

def analyze_phase_impact(freqx, freqy, num_points=361):
    # 生成相位序列
    phases = np.linspace(0, 360, num_points)
    
    # 存储填充率结果
    x_phase_fill_rates = []
    y_phase_fill_rates = []
    
    # 计算x相位变化的填充率
    for phase in phases:
        image = simulate_lissajous(freqx, freqy, phase, 0)
        x_phase_fill_rates.append(cal_fill_rate(image))
    
    # 计算y相位变化的填充率
    for phase in phases:
        image = simulate_lissajous(freqx, freqy, 0, phase)
        y_phase_fill_rates.append(cal_fill_rate(image))
    
    # 找到最大值及其对应的相位
    x_max_idx = np.argmax(x_phase_fill_rates)
    y_max_idx = np.argmax(y_phase_fill_rates)
    x_max_phase = phases[x_max_idx]
    y_max_phase = phases[y_max_idx]
    x_max_fill = x_phase_fill_rates[x_max_idx]
    y_max_fill = y_phase_fill_rates[y_max_idx]
    
    # 创建图形和第一个y轴
    fig, ax1 = plt.subplots(facecolor='black')
    ax1.set_facecolor('black')
    
    # 绘制x相位的填充率（蓝色）
    ax1.plot(phases, x_phase_fill_rates, 'b-', label='X Phase')
    # 标注x相位最大值点
    ax1.scatter(x_max_phase, x_max_fill, color='cyan', s=100, zorder=5)
    ax1.annotate(f'X Max: {x_max_fill:.2%}\nPhase: {x_max_phase:.1f}°',
                 xy=(x_max_phase, x_max_fill), xytext=(10, 10),
                 textcoords='offset points', color='cyan',
                 bbox=dict(facecolor='black', edgecolor='cyan', alpha=0.7))
    
    ax1.set_xlabel('Phase (degrees)', color='white')
    ax1.set_ylabel('Fill Rate (X Phase)', color='b')
    ax1.tick_params(axis='y', labelcolor='b')
    ax1.tick_params(colors='white', which='both')
    
    # 创建第二个y轴
    ax2 = ax1.twinx()
    
    # 绘制y相位的填充率（红色）
    ax2.plot(phases, y_phase_fill_rates, 'r-', label='Y Phase')
    # 标注y相位最大值点
    ax2.scatter(y_max_phase, y_max_fill, color='yellow', s=100, zorder=5)
    ax2.annotate(f'Y Max: {y_max_fill:.2%}\nPhase: {y_max_phase:.1f}°',
                 xy=(y_max_phase, y_max_fill), xytext=(10, -20),
                 textcoords='offset points', color='yellow',
                 bbox=dict(facecolor='black', edgecolor='yellow', alpha=0.7))
    
    ax2.set_ylabel('Fill Rate (Y Phase)', color='r')
    ax2.tick_params(axis='y', labelcolor='r')
    
    # 设置标题和图例
    plt.title(f'Fill Rate vs Phase Change\nfreqx={freqx}, freqy={freqy}', color='white')
    
    # 添加图例
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper right')
    
    # 保存图像
    plt.savefig(f'phase_impact_fx={freqx}_fy={freqy}.png', 
                bbox_inches='tight',
                facecolor='black',
                edgecolor='none')
    
    plt.show()
    
    # 返回最优相位值
    return {
        'x_best_phase': x_max_phase,
        'x_max_fill_rate': x_max_fill,
        'y_best_phase': y_max_phase,
        'y_max_fill_rate': y_max_fill
    }


if __name__ == "__main__":
    freqx = 11390  # Example frequency for X
    freqy = 3790  # Example frequency for Y
    phasex_deg = 0  # Example phase for X
    phasey_deg = 12 # Example phase for Y


    lissajous_image = simulate_lissajous(freqx, freqy, phasex_deg, phasey_deg)


    display_lissajous(lissajous_image, freqx, freqy, phasex_deg, phasey_deg)



    #################################################

    #################################################

    analyze_phase_impact(freqx, freqy)
    

    # calculate the fill rate with random phase for 100times and plot the boxplot
    # fill_rates = []
    # for _ in range(100):
    #     phasex_deg = np.random.randint(0, 360)
    #     phasey_deg = np.random.randint(0, 360)
    #     lissajous_image = simulate_lissajous(freqx, freqy, phasex_deg, phasey_deg)
    #     fill_rates.append(cal_fill_rate(lissajous_image))
    # plt.boxplot(fill_rates)
    # plt.title('Boxplot of Fill Rate with Random Phase')
    # plt.ylabel('Fill Rate')
    # plt.savefig('boxplot_fill_rate_random_phase.png', bbox_inches='tight')
    # plt.show()

