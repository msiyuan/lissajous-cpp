import numpy as np
import cv2
from scipy import optimize
from scipy.ndimage import label, center_of_mass
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib import cm
import warnings

def gaussian_2d(xy, amplitude, x0, y0, sigma_x, sigma_y, theta, offset):
    """二维高斯函数"""
    x, y = xy
    a = (np.cos(theta)**2)/(2*sigma_x**2) + (np.sin(theta)**2)/(2*sigma_y**2)
    b = -(np.sin(2*theta))/(4*sigma_x**2) + (np.sin(2*theta))/(4*sigma_y**2)
    c = (np.sin(theta)**2)/(2*sigma_x**2) + (np.cos(theta)**2)/(2*sigma_y**2)
    return offset + amplitude * np.exp(-(a*(x-x0)**2 + 2*b*(x-x0)*(y-y0) + c*(y-y0)**2))

def segment_bright_spots(image, threshold_factor=0.7, min_area=10, roi_size=50):
    """
    分割亮斑并提取相同大小的ROI
    
    Parameters:
    - image: 16位单通道灰度图
    - threshold_factor: 阈值因子（相对于最大值）
    - min_area: 最小亮斑面积
    - roi_size: ROI边长（像素）
    
    Returns:
    - rois: 提取的ROI列表
    - centers: 亮斑中心坐标列表
    """
    # 归一化到0-255用于处理
    normalized = cv2.normalize(image.astype(np.float32), None, 0, 255, cv2.NORM_MINMAX)
    
    # 动态阈值分割
    threshold = np.max(normalized) * threshold_factor
    binary = (normalized > threshold).astype(np.uint8)
    
    # 形态学操作清理噪声
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    
    # 连通域分析
    labeled_array, num_features = label(binary)
    
    rois = []
    centers = []
    
    for i in range(1, num_features + 1):
        mask = (labeled_array == i)
        area = np.sum(mask)
        
        if area < min_area:
            continue
            
        # 计算质心
        cy, cx = center_of_mass(mask)
        
        # 确保ROI在图像范围内
        half_size = roi_size // 2
        y1 = max(0, int(cy - half_size))
        y2 = min(image.shape[0], int(cy + half_size))
        x1 = max(0, int(cx - half_size))
        x2 = min(image.shape[1], int(cx + half_size))
        
        # 提取ROI并调整到统一大小
        roi = image[y1:y2, x1:x2]
        if roi.shape[0] < roi_size or roi.shape[1] < roi_size:
            # 零填充到目标大小
            padded_roi = np.zeros((roi_size, roi_size), dtype=image.dtype)
            pad_y = (roi_size - roi.shape[0]) // 2
            pad_x = (roi_size - roi.shape[1]) // 2
            padded_roi[pad_y:pad_y+roi.shape[0], pad_x:pad_x+roi.shape[1]] = roi
            roi = padded_roi
        elif roi.shape[0] > roi_size or roi.shape[1] > roi_size:
            # 裁剪到目标大小
            crop_y = (roi.shape[0] - roi_size) // 2
            crop_x = (roi.shape[1] - roi_size) // 2
            roi = roi[crop_y:crop_y+roi_size, crop_x:crop_x+roi_size]
        
        rois.append(roi)
        centers.append((cx, cy))
    
    return rois, centers

def fit_gaussian_2d(roi):
    """
    对ROI进行二维高斯拟合
    
    Parameters:
    - roi: 图像ROI
    
    Returns:
    - fitted_params: 拟合参数
    - fitted_surface: 拟合的高斯曲面
    - r_squared: 拟合优度
    """
    h, w = roi.shape
    x = np.arange(w)
    y = np.arange(h)
    X, Y = np.meshgrid(x, y)
    
    # 初始参数估计
    amplitude_init = np.max(roi) - np.min(roi)
    x0_init = w / 2
    y0_init = h / 2
    sigma_init = min(w, h) / 6
    offset_init = np.min(roi)
    
    initial_guess = [amplitude_init, x0_init, y0_init, sigma_init, sigma_init, 0, offset_init]
    
    try:
        # 拟合
        popt, pcov = optimize.curve_fit(
            lambda xy, *p: gaussian_2d(xy, *p).ravel(),
            (X.ravel(), Y.ravel()),
            roi.ravel(),
            p0=initial_guess,
            maxfev=5000
        )
        
        # 计算拟合曲面
        fitted_surface = gaussian_2d((X, Y), *popt)
        
        # 计算R²
        ss_res = np.sum((roi - fitted_surface) ** 2)
        ss_tot = np.sum((roi - np.mean(roi)) ** 2)
        r_squared = 1 - (ss_res / ss_tot)
        
        return popt, fitted_surface, r_squared
        
    except Exception as e:
        print(f"拟合失败: {e}")
        return None, None, 0

def calculate_fwhm_area(params):
    """
    计算半高宽面积
    
    Parameters:
    - params: 高斯拟合参数 [amplitude, x0, y0, sigma_x, sigma_y, theta, offset]
    
    Returns:
    - fwhm_area: 半高宽面积（像素²）
    """
    amplitude, x0, y0, sigma_x, sigma_y, theta, offset = params
    
    # FWHM = 2 * sqrt(2 * ln(2)) * sigma ≈ 2.355 * sigma
    fwhm_factor = 2 * np.sqrt(2 * np.log(2))
    fwhm_x = fwhm_factor * sigma_x
    fwhm_y = fwhm_factor * sigma_y
    
    # 椭圆面积 = π * a * b，其中a和b是半轴长度
    fwhm_area = np.pi * (fwhm_x / 2) * (fwhm_y / 2)
    
    return fwhm_area

def visualize_3d_surface(roi, fitted_surface, title="高斯拟合结果"):
    """
    三维可视化原始数据和拟合曲面
    """
    h, w = roi.shape
    x = np.arange(w)
    y = np.arange(h)
    X, Y = np.meshgrid(x, y)
    
    fig = plt.figure(figsize=(15, 5))
    
    # 原始数据
    ax1 = fig.add_subplot(131, projection='3d')
    surf1 = ax1.plot_surface(X, Y, roi, cmap=cm.viridis, alpha=0.8)
    ax1.set_title('原始亮斑')
    ax1.set_xlabel('X (像素)')
    ax1.set_ylabel('Y (像素)')
    ax1.set_zlabel('灰度值')
    
    # 拟合曲面
    ax2 = fig.add_subplot(132, projection='3d')
    surf2 = ax2.plot_surface(X, Y, fitted_surface, cmap=cm.plasma, alpha=0.8)
    ax2.set_title('高斯拟合曲面')
    ax2.set_xlabel('X (像素)')
    ax2.set_ylabel('Y (像素)')
    ax2.set_zlabel('灰度值')
    
    # 残差
    ax3 = fig.add_subplot(133, projection='3d')
    residual = roi - fitted_surface
    surf3 = ax3.plot_surface(X, Y, residual, cmap=cm.coolwarm, alpha=0.8)
    ax3.set_title('拟合残差')
    ax3.set_xlabel('X (像素)')
    ax3.set_ylabel('Y (像素)')
    ax3.set_zlabel('残差')
    
    plt.tight_layout()
    plt.show()

def analyze_bright_spots(image_path, threshold_factor=0.7, roi_size=50, visualize=True):
    """
    主函数：分析图像中的亮斑
    
    Parameters:
    - image_path: 图像路径
    - threshold_factor: 分割阈值因子
    - roi_size: ROI大小
    - visualize: 是否显示可视化结果
    
    Returns:
    - results: 分析结果字典列表
    """
    # 读取16位灰度图像
    image = cv2.imread(image_path, cv2.IMREAD_ANYDEPTH | cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError(f"无法读取图像: {image_path}")
    
    print(f"图像尺寸: {image.shape}")
    print(f"图像位深: {image.dtype}")
    print(f"灰度值范围: {np.min(image)} - {np.max(image)}")
    
    # 分割亮斑
    rois, centers = segment_bright_spots(image, threshold_factor, roi_size=roi_size)
    print(f"检测到 {len(rois)} 个亮斑")
    
    results = []
    
    for i, (roi, center) in enumerate(zip(rois, centers)):
        print(f"\n分析亮斑 {i+1}/{len(rois)}")
        
        # 计算平均值
        mean_intensity = np.mean(roi)
        
        # 高斯拟合
        params, fitted_surface, r_squared = fit_gaussian_2d(roi)
        
        if params is not None:
            # 计算半高宽面积
            fwhm_area = calculate_fwhm_area(params)
            
            result = {
                'spot_id': i + 1,
                'center': center,
                'mean_intensity': mean_intensity,
                'gaussian_params': {
                    'amplitude': params[0],
                    'x0': params[1],
                    'y0': params[2],
                    'sigma_x': params[3],
                    'sigma_y': params[4],
                    'theta': params[5],
                    'offset': params[6]
                },
                'r_squared': r_squared,
                'fwhm_area': fwhm_area,
                'roi': roi,
                'fitted_surface': fitted_surface
            }
            
            results.append(result)
            
            print(f"  平均灰度值: {mean_intensity:.2f}")
            print(f"  拟合优度 R²: {r_squared:.4f}")
            print(f"  半高宽面积: {fwhm_area:.2f} 像素²")
            print(f"  高斯参数: 振幅={params[0]:.2f}, σx={params[3]:.2f}, σy={params[4]:.2f}")
            
            # 可视化
            if visualize:
                visualize_3d_surface(roi, fitted_surface, f"亮斑 {i+1}")
        else:
            print(f"  亮斑 {i+1} 拟合失败")
    
    return results

# 示例使用
if __name__ == "__main__":
    # 使用示例
    results = analyze_bright_spots("D:\code\Lissajous_scan_git\Lissajous_sacn\FOV_test_data\FOV_ybmsy\\beads380\\43um\AVG_fig_beads_phase_355_346_png.tif")
    
    