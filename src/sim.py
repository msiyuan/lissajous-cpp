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


if __name__ == "__main__":
    freqx = 11390  # Example frequency for X
    freqy = 3790  # Example frequency for Y
    phasex_deg = 0  # Example phase for X
    phasey_deg = 0  # Example phase for Y


    lissajous_image = simulate_lissajous(freqx, freqy, phasex_deg, phasey_deg)


    display_lissajous(lissajous_image, freqx, freqy, phasex_deg, phasey_deg)
    

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

