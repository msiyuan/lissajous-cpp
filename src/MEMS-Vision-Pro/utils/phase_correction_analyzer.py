"""
相位校正频域分析工具
用于分析相位校正图像的频域特征
"""

import os
import numpy as np
import cv2
import matplotlib.pyplot as plt
from scipy.fft import fft2, fftshift

def apply_window(img):
    """加汉宁窗，减少FFT边缘伪影"""
    M, N = img.shape
    win = np.outer(np.hanning(M), np.hanning(N))
    return img * win

def compute_spectrum(img):
    """计算2D FFT功率谱"""
    imgw = apply_window(img)
    F = fftshift(fft2(imgw))
    P = np.abs(F)**2
    return P, F

def spectral_metrics_from_P(P, r_frac=0.25, dc_mask_frac=0.02):
    """基础频域指标: SC_r, Centroid"""
    M, N = P.shape
    uy = np.arange(-M//2, M//2)
    vx = np.arange(-N//2, N//2)
    U, V = np.meshgrid(vx, uy)
    R = np.sqrt(U.astype(float)**2 + V.astype(float)**2)
    Rmax = R.max()
    r = r_frac * Rmax
    # mask掉DC区域
    dc_mask = R <= (dc_mask_frac * Rmax)
    P_masked = P.copy()
    P_masked[dc_mask] = 0.0
    Psum_masked = P_masked.sum() + 1e-12

    SC_r = P_masked[R <= r].sum() / Psum_masked
    centroid = (R * P_masked).sum() / Psum_masked
    return {'SC_r': SC_r, 'centroid': centroid}

def extra_spectral_metrics(P):
    """新增频域指标: 峰度, 方差, 各向异性"""
    M, N = P.shape
    uy = np.arange(-M//2, M//2)
    vx = np.arange(-N//2, N//2)
    U, V = np.meshgrid(vx, uy)
    R = np.sqrt(U**2 + V**2)
    Theta = np.arctan2(V, U)

    Psum = P.sum() + 1e-12
    meanR = (R * P).sum() / Psum
    varR = ((R - meanR)**2 * P).sum() / Psum  # 半径能量方差
    kurtosis = ((R - meanR)**4 * P).sum() / (Psum * (varR**2 + 1e-12))  # 峰度

    # 各向异性（角度能量分布方差）
    nbins = 90
    ang_bins = np.linspace(-np.pi, np.pi, nbins)
    ang_energy = np.array([
        P[(Theta >= a1) & (Theta < a2)].sum()
        for a1, a2 in zip(ang_bins[:-1], ang_bins[1:])
    ])
    anisotropy = np.var(ang_energy / (ang_energy.sum() + 1e-12))

    return {'varR': varR, 'kurtosis': kurtosis, 'anisotropy': anisotropy}

def read_tiff_any(image_path):
    """读取任意tiff"""
    img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"无法读取图像 {image_path}")
    if img.ndim == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img.astype(np.float64)

def analyze_folder_freq_metrics(folder_path, r_frac=0.25, save_plots=True):
    """
    分析文件夹中图像的频域特征
    
    Args:
        folder_path: 图像文件夹路径
        r_frac: 中心区域半径比例
        save_plots: 是否保存图表
        
    Returns:
        list: 分析结果列表
    """
    files = sorted([f for f in os.listdir(folder_path) if f.lower().endswith('.tif') or f.lower().endswith('.tiff')])
    if not files:
        print("❌ 未找到任何tiff文件")
        return []

    results = []
    for f in files:
        try:
            path = os.path.join(folder_path, f)
            img = read_tiff_any(path)
            img = img - img.mean()

            P, _ = compute_spectrum(img)
            base = spectral_metrics_from_P(P, r_frac=r_frac)
            extra = extra_spectral_metrics(P)
            base.update(extra)
            base['name'] = f
            results.append(base)
        except Exception as e:
            print(f"处理图像 {f} 时出错: {e}")
            continue

    if not results:
        print("没有成功处理的图像")
        return []

    # 绘图
    if save_plots:
        # 从文件名中提取相位值作为横坐标
        phases = []
        for r in results:
            name = r['name']
            # 从文件名中提取相位值，例如从"x_phase_-0.1_deg.tiff"中提取-0.1
            if 'x_phase_' in name:
                phase_str = name.split('x_phase_')[1].split('_deg')[0]
                phase = float(phase_str)
            elif 'y_phase_' in name:
                phase_str = name.split('y_phase_')[1].split('_deg')[0]
                phase = float(phase_str)
            else:
                # 如果无法解析相位值，则使用索引
                phase = len(phases)
            phases.append(phase)
        
        # 按相位值排序
        sorted_indices = np.argsort(phases)
        phases = np.array(phases)[sorted_indices]
        sorted_results = [results[i] for i in sorted_indices]
        
        fig, axes = plt.subplots(4, 1, figsize=(12, 10), sharex=True)

        axes[0].plot(phases, [r['SC_r'] for r in sorted_results], 'o-', label='SC_r (↑)')
        axes[0].set_ylabel('SC_r')
        axes[0].legend()
        axes[0].grid(True)

        axes[1].plot(phases, [r['centroid'] for r in sorted_results], 'o-', label='Centroid (↓)')
        axes[1].set_ylabel('Centroid')
        axes[1].legend()
        axes[1].grid(True)

        axes[2].plot(phases, [r['kurtosis'] for r in sorted_results], 'o-', label='Spectral Kurtosis (↑)')
        axes[2].set_ylabel('Kurtosis')
        axes[2].legend()
        axes[2].grid(True)

        axes[3].plot(phases, [r['anisotropy'] for r in sorted_results], 'o-', label='Anisotropy (↓)')
        axes[3].set_ylabel('Anisotropy')
        axes[3].set_xlabel('相位值 (度)')
        axes[3].legend()
        axes[3].grid(True)
        
        # 设置横坐标刻度，确保显示实际相位值
        if len(phases) > 0:
            min_phase = np.min(phases)
            max_phase = np.max(phases)
            # 设置合适的刻度间隔
            phase_range = max_phase - min_phase
            if phase_range <= 1.0:
                tick_spacing = 0.1
            elif phase_range <= 2.0:
                tick_spacing = 0.2
            elif phase_range <= 5.0:
                tick_spacing = 0.5
            else:
                tick_spacing = 1.0
            # 生成刻度值
            tick_values = np.arange(min_phase, max_phase + tick_spacing/2, tick_spacing)
            axes[3].set_xticks(tick_values)
            # 确保刻度标签显示为浮点数格式
            axes[3].set_xticklabels([f"{x:.1f}" for x in tick_values])

        plt.tight_layout()
        
        # 保存图表
        plot_path = os.path.join(folder_path, 'freq_analysis.png')
        plt.savefig(plot_path, dpi=300, bbox_inches='tight')
        plt.close()

    # 保存结果到CSV文件
    csv_path = os.path.join(folder_path, 'freq_metrics.csv')
    with open(csv_path, 'w') as f:
        # 写入表头
        headers = ['name', 'SC_r', 'centroid', 'varR', 'kurtosis', 'anisotropy']
        f.write(','.join(headers) + '\n')
        
        # 写入数据
        for r in results:
            values = [r['name'], 
                     f"{r['SC_r']:.6f}", 
                     f"{r['centroid']:.6f}", 
                     f"{r['varR']:.6f}", 
                     f"{r['kurtosis']:.6f}", 
                     f"{r['anisotropy']:.6e}"]
            f.write(','.join(values) + '\n')

    return results

def analyze_phase_correction_results(base_path="./phaseCorrect"):
    """
    分析相位校正结果
    
    Args:
        base_path: 相位校正结果根目录
    """
    # 分析X相位文件夹
    x_folder = os.path.join(base_path, "x")
    if os.path.exists(x_folder):
        print("分析X相位校正结果...")
        analyze_folder_freq_metrics(x_folder)
    
    # 分析Y相位文件夹
    y_folder = os.path.join(base_path, "y")
    if os.path.exists(y_folder):
        print("分析Y相位校正结果...")
        analyze_folder_freq_metrics(y_folder)