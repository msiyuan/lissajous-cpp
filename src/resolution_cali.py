import numpy as np
import cv2
from scipy import optimize
from scipy.ndimage import gaussian_filter
from skimage.feature import peak_local_max
import matplotlib.pyplot as plt
import matplotlib
from typing import List, Tuple, Dict
import warnings
import platform
warnings.filterwarnings('ignore')

# 配置中文字体显示
def setup_chinese_font():
    """配置matplotlib中文字体"""
    system = platform.system()
    if system == "Windows":
        matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
    elif system == "Darwin":  # macOS
        matplotlib.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'PingFang SC', 'STHeiti']
    else:  # Linux
        matplotlib.rcParams['font.sans-serif'] = ['DejaVu Sans', 'WenQuanYi Micro Hei', 'SimHei']
    
    matplotlib.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

# 初始化字体配置
setup_chinese_font()

class FluorescentBeadCalibration:
    def __init__(self, image_path: str, physical_size_um: float = 43.0, image_size_px: int = 512):
        """
        初始化荧光珠校准类
        
        Args:
            image_path: 16位灰度图像路径
            physical_size_um: 图像物理尺寸(微米)
            image_size_px: 图像像素尺寸
        """
        self.image_path = image_path
        self.physical_size_um = physical_size_um
        self.image_size_px = image_size_px
        self.pixel_size_um = physical_size_um / image_size_px
        self.image = None
        self.bead_positions = []
        self.gaussian_params = []
        
    def load_image(self) -> np.ndarray:
        """加载16位灰度图像"""
        self.image = cv2.imread(self.image_path, cv2.IMREAD_UNCHANGED)
        if self.image is None:
            raise ValueError(f"无法加载图像: {self.image_path}")
        
        # 确保是16位单通道
        if len(self.image.shape) == 3:
            self.image = cv2.cvtColor(self.image, cv2.COLOR_BGR2GRAY)
        
        return self.image
    
    def detect_beads(self, min_distance: int = 20, threshold_abs: float = None, 
                     threshold_percentile: float = 95, show_debug: bool = True) -> List[Tuple[int, int]]:
        """
        检测荧光珠位置
        
        Args:
            min_distance: 峰值间最小距离
            threshold_abs: 绝对阈值，None时自动计算
            threshold_percentile: 阈值百分位数
            show_debug: 是否显示调试信息
        """
        if self.image is None:
            raise ValueError("请先加载图像")
        
        # 预处理：轻微高斯滤波减少噪声
        filtered = gaussian_filter(self.image.astype(np.float32), sigma=1.0)
        
        # 计算图像统计信息
        img_min = np.min(self.image)
        img_max = np.max(self.image)
        img_mean = np.mean(self.image)
        img_std = np.std(self.image)
        
        # 自动计算阈值
        if threshold_abs is None:
            threshold_abs = np.percentile(filtered, threshold_percentile)
        
        if show_debug:
            print(f"=== 图像统计信息 ===")
            print(f"图像尺寸: {self.image.shape}")
            print(f"像素值范围: {img_min} - {img_max}")
            print(f"平均值: {img_mean:.2f}")
            print(f"标准差: {img_std:.2f}")
            print(f"阈值百分位({threshold_percentile}%): {threshold_abs:.2f}")
            print(f"检测最小距离: {min_distance} 像素")
            
            # 计算不同百分位的阈值供参考
            percentiles = [90, 95, 98, 99, 99.5]
            print("参考阈值:")
            for p in percentiles:
                thresh = np.percentile(filtered, p)
                print(f"  {p}%: {thresh:.2f}")
        
        # 尝试多种检测方法
        try:
            # 方法1: 使用peak_local_max
            coordinates = peak_local_max(
                filtered, 
                min_distance=min_distance,
                threshold_abs=threshold_abs,
                exclude_border=True
            )
            
            if show_debug:
                print(f"方法1 (peak_local_max) 检测到: {len(coordinates)} 个峰值")
            
            # 如果检测不到，尝试降低阈值
            if len(coordinates) == 0:
                lower_percentiles = [90, 85, 80, 75, 70]
                for p in lower_percentiles:
                    threshold_lower = np.percentile(filtered, p)
                    coordinates = peak_local_max(
                        filtered, 
                        min_distance=min_distance,
                        threshold_abs=threshold_lower,
                        exclude_border=True
                    )
                    if show_debug:
                        print(f"尝试{p}%阈值({threshold_lower:.2f}): {len(coordinates)} 个峰值")
                    if len(coordinates) > 0:
                        threshold_abs = threshold_lower
                        break
            
            # 如果还是检测不到，尝试方法2: 基于标准差的阈值
            if len(coordinates) == 0:
                threshold_std = img_mean + 2 * img_std
                coordinates = peak_local_max(
                    filtered, 
                    min_distance=min_distance,
                    threshold_abs=threshold_std,
                    exclude_border=True
                )
                if show_debug:
                    print(f"方法2 (mean+2*std={threshold_std:.2f}): {len(coordinates)} 个峰值")
                threshold_abs = threshold_std
            
            # 如果还是检测不到，减小最小距离
            if len(coordinates) == 0:
                smaller_distances = [15, 10, 8, 5]
                for dist in smaller_distances:
                    coordinates = peak_local_max(
                        filtered, 
                        min_distance=dist,
                        threshold_abs=img_mean + img_std,
                        exclude_border=True
                    )
                    if show_debug:
                        print(f"减小距离到{dist}像素: {len(coordinates)} 个峰值")
                    if len(coordinates) > 0:
                        min_distance = dist
                        break
            
        except Exception as e:
            print(f"检测过程出错: {e}")
            coordinates = []
        
        self.bead_positions = [(coord[1], coord[0]) for coord in coordinates]
        
        if show_debug:
            print(f"\n=== 最终检测结果 ===")
            print(f"使用阈值: {threshold_abs:.2f}")
            print(f"使用最小距离: {min_distance} 像素")
            print(f"检测到 {len(self.bead_positions)} 个荧光珠")
            
            if len(self.bead_positions) > 0:
                print("前5个荧光珠位置:")
                for i, pos in enumerate(self.bead_positions[:5]):
                    intensity = self.image[pos[1], pos[0]]
                    print(f"  {i+1}: ({pos[0]}, {pos[1]}) - 强度: {intensity}")
        
        return self.bead_positions
    
    def gaussian_2d(self, xy: Tuple[np.ndarray, np.ndarray], amplitude: float, 
                   x0: float, y0: float, sigma_x: float, sigma_y: float, 
                   theta: float, offset: float) -> np.ndarray:
        """
        二维高斯函数
        
        Args:
            xy: (x, y) 坐标网格
            amplitude: 幅度
            x0, y0: 中心坐标
            sigma_x, sigma_y: x和y方向标准差
            theta: 旋转角度
            offset: 偏移量
        """
        x, y = xy
        x0, y0 = float(x0), float(y0)
        
        cos_theta = np.cos(theta)
        sin_theta = np.sin(theta)
        
        a = (cos_theta**2) / (2*sigma_x**2) + (sin_theta**2) / (2*sigma_y**2)
        b = -(sin_theta * cos_theta) / (2*sigma_x**2) + (sin_theta * cos_theta) / (2*sigma_y**2)
        c = (sin_theta**2) / (2*sigma_x**2) + (cos_theta**2) / (2*sigma_y**2)
        
        g = offset + amplitude * np.exp(-(a*(x-x0)**2 + 2*b*(x-x0)*(y-y0) + c*(y-y0)**2))
        
        return g.ravel()
    
    def fit_single_bead(self, center: Tuple[int, int], roi_size: int = 20) -> Dict:
        """
        对单个荧光珠进行二维高斯拟合
        
        Args:
            center: 荧光珠中心坐标
            roi_size: ROI大小的一半
        """
        x_center, y_center = center
        
        # 提取ROI
        x_min = max(0, x_center - roi_size)
        x_max = min(self.image.shape[1], x_center + roi_size)
        y_min = max(0, y_center - roi_size)
        y_max = min(self.image.shape[0], y_center + roi_size)
        
        roi = self.image[y_min:y_max, x_min:x_max].astype(np.float32)
        
        if roi.size == 0:
            return None
        
        # 创建坐标网格
        x = np.arange(roi.shape[1])
        y = np.arange(roi.shape[0])
        x, y = np.meshgrid(x, y)
        
        # 初始参数估计
        amplitude_init = np.max(roi) - np.min(roi)
        x0_init = roi.shape[1] / 2
        y0_init = roi.shape[0] / 2
        sigma_init = 3.0
        theta_init = 0.0
        offset_init = np.min(roi)
        
        initial_guess = [amplitude_init, x0_init, y0_init, sigma_init, sigma_init, theta_init, offset_init]
        
        try:
            # 拟合
            popt, pcov = optimize.curve_fit(
                self.gaussian_2d, 
                (x, y), 
                roi.ravel(),
                p0=initial_guess,
                maxfev=2000
            )
            
            amplitude, x0, y0, sigma_x, sigma_y, theta, offset = popt
            
            # 确保sigma为正值
            sigma_x = abs(sigma_x)
            sigma_y = abs(sigma_y)
            
            return {
                'amplitude': amplitude,
                'x0': x0 + x_min,
                'y0': y0 + y_min,
                'sigma_x': sigma_x,
                'sigma_y': sigma_y,
                'theta': theta,
                'offset': offset,
                'fit_success': True
            }
            
        except Exception as e:
            print(f"拟合失败 at {center}: {e}")
            return {'fit_success': False}
    
    def fit_all_beads(self, roi_size: int = 20) -> List[Dict]:
        """对所有检测到的荧光珠进行拟合"""
        if not self.bead_positions:
            raise ValueError("请先检测荧光珠位置")
        
        self.gaussian_params = []
        
        for i, position in enumerate(self.bead_positions):
            print(f"拟合荧光珠 {i+1}/{len(self.bead_positions)}")
            params = self.fit_single_bead(position, roi_size)
            if params and params['fit_success']:
                self.gaussian_params.append(params)
        
        print(f"成功拟合 {len(self.gaussian_params)} 个荧光珠")
        return self.gaussian_params
    
    def calculate_average_fwhm_area(self) -> Dict:
        """计算平均的二维高斯半高面积"""
        if not self.gaussian_params:
            raise ValueError("请先进行高斯拟合")
        
        # 提取所有成功拟合的参数
        sigma_x_list = [p['sigma_x'] for p in self.gaussian_params]
        sigma_y_list = [p['sigma_y'] for p in self.gaussian_params]
        
        # 计算平均sigma
        avg_sigma_x = np.mean(sigma_x_list)
        avg_sigma_y = np.mean(sigma_y_list)
        
        # 转换为物理单位(微米)
        avg_sigma_x_um = avg_sigma_x * self.pixel_size_um
        avg_sigma_y_um = avg_sigma_y * self.pixel_size_um
        
        # 计算FWHM (Full Width at Half Maximum)
        # FWHM = 2 * sqrt(2 * ln(2)) * sigma ≈ 2.355 * sigma
        fwhm_factor = 2 * np.sqrt(2 * np.log(2))
        fwhm_x_um = fwhm_factor * avg_sigma_x_um
        fwhm_y_um = fwhm_factor * avg_sigma_y_um
        
        # 计算半高面积 (椭圆面积 = π * a * b, 其中a和b是半轴长度)
        # 对于FWHM，半轴长度就是FWHM/2
        fwhm_area_um2 = np.pi * (fwhm_x_um / 2) * (fwhm_y_um / 2)
        
        # 计算等效直径（假设为圆形）
        equivalent_diameter_um = 2 * np.sqrt(fwhm_area_um2 / np.pi)
        
        results = {
            'avg_sigma_x_px': avg_sigma_x,
            'avg_sigma_y_px': avg_sigma_y,
            'avg_sigma_x_um': avg_sigma_x_um,
            'avg_sigma_y_um': avg_sigma_y_um,
            'fwhm_x_um': fwhm_x_um,
            'fwhm_y_um': fwhm_y_um,
            'fwhm_area_um2': fwhm_area_um2,
            'equivalent_diameter_um': equivalent_diameter_um,
            'num_beads_fitted': len(self.gaussian_params),
            'pixel_size_um': self.pixel_size_um
        }
        
        return results
    
    def visualize_results(self, save_path: str = None):
        """可视化结果"""
        fig, axes = plt.subplots(2, 2, figsize=(12, 10))
        
        # 原始图像和检测到的荧光珠
        axes[0, 0].imshow(self.image, cmap='gray')
        if self.bead_positions:
            x_coords = [pos[0] for pos in self.bead_positions]
            y_coords = [pos[1] for pos in self.bead_positions]
            axes[0, 0].scatter(x_coords, y_coords, c='red', marker='+', s=100)
        axes[0, 0].set_title(f'Detected Fluorescent Beads ({len(self.bead_positions)} beads)')
        axes[0, 0].set_xlabel('X (pixels)')
        axes[0, 0].set_ylabel('Y (pixels)')
        
        # Sigma分布
        if self.gaussian_params:
            sigma_x = [p['sigma_x'] for p in self.gaussian_params]
            sigma_y = [p['sigma_y'] for p in self.gaussian_params]
            
            axes[0, 1].hist(sigma_x, alpha=0.5, label='Sigma X', bins=10)
            axes[0, 1].hist(sigma_y, alpha=0.5, label='Sigma Y', bins=10)
            axes[0, 1].set_xlabel('Sigma (pixels)')
            axes[0, 1].set_ylabel('Frequency')
            axes[0, 1].set_title('Sigma Distribution')
            axes[0, 1].legend()
            
            # 散点图
            axes[1, 0].scatter(sigma_x, sigma_y)
            axes[1, 0].set_xlabel('Sigma X (pixels)')
            axes[1, 0].set_ylabel('Sigma Y (pixels)')
            axes[1, 0].set_title('Sigma X vs Sigma Y')
            
            # 结果总结
            results = self.calculate_average_fwhm_area()
            text = f"""Analysis Results:
Fitted beads: {results['num_beads_fitted']}
Avg FWHM X: {results['fwhm_x_um']:.3f} μm
Avg FWHM Y: {results['fwhm_y_um']:.3f} μm
FWHM Area: {results['fwhm_area_um2']:.3f} μm²
Equiv. Diameter: {results['equivalent_diameter_um']:.3f} μm
Pixel Size: {results['pixel_size_um']:.3f} μm/px"""
            
            axes[1, 1].text(0.1, 0.5, text, transform=axes[1, 1].transAxes, 
                           fontsize=10, verticalalignment='center', fontfamily='monospace')
            axes[1, 1].set_title('Analysis Results')
            axes[1, 1].axis('off')
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()
    
    def show_detection_preview(self, min_distance: int = 20, threshold_percentile: float = 95):
        """显示检测预览，帮助调试参数"""
        if self.image is None:
            self.load_image()
        
        # 预处理
        filtered = gaussian_filter(self.image.astype(np.float32), sigma=1.0)
        
        fig, axes = plt.subplots(2, 3, figsize=(15, 10))
        
        # 原始图像
        axes[0, 0].imshow(self.image, cmap='gray')
        axes[0, 0].set_title('Original Image')
        axes[0, 0].set_xlabel('X (pixels)')
        axes[0, 0].set_ylabel('Y (pixels)')
        
        # 滤波后图像
        axes[0, 1].imshow(filtered, cmap='gray')
        axes[0, 1].set_title('After Gaussian Filter')
        
        # 强度直方图
        axes[0, 2].hist(self.image.ravel(), bins=100, alpha=0.7, label='Original')
        axes[0, 2].hist(filtered.ravel(), bins=100, alpha=0.7, label='Filtered')
        axes[0, 2].axvline(np.percentile(filtered, threshold_percentile), 
                          color='red', linestyle='--', label=f'{threshold_percentile}% Threshold')
        axes[0, 2].set_xlabel('Intensity')
        axes[0, 2].set_ylabel('Frequency')
        axes[0, 2].set_title('Intensity Distribution')
        axes[0, 2].legend()
        axes[0, 2].set_yscale('log')
        
        # 测试不同阈值
        percentiles = [90, 95, 98, 99]
        for i, p in enumerate(percentiles):
            thresh = np.percentile(filtered, p)
            coordinates = peak_local_max(
                filtered, 
                min_distance=min_distance,
                threshold_abs=thresh,
                exclude_border=True
            )
            
            ax = axes[1, i] if i < 3 else axes[1, 2]
            ax.imshow(self.image, cmap='gray')
            if len(coordinates) > 0:
                ax.scatter(coordinates[:, 1], coordinates[:, 0], 
                          c='red', marker='+', s=50, alpha=0.8)
            ax.set_title(f'{p}% Threshold: {len(coordinates)} points')
            
        # 如果第4个图没用到，显示检测区域信息
        if len(percentiles) <= 3:
            axes[1, 2].text(0.1, 0.5, f"""Detection Parameters:
Min Distance: {min_distance} pixels
Physical Distance: {min_distance * self.pixel_size_um:.2f} μm

Adjustment Suggestions:
1. Lower threshold percentile if too few detections
2. Increase min distance if too many detections
3. Check if image loaded correctly""", 
                           transform=axes[1, 2].transAxes, fontsize=10, fontfamily='monospace')
            axes[1, 2].set_title('Detection Suggestions')
            axes[1, 2].axis('off')
        
        plt.tight_layout()
        plt.show()
    
    def run_full_analysis(self, min_distance: int = 20, roi_size: int = 20, 
                         threshold_percentile: float = 95, show_preview: bool = False) -> Dict:
        """运行完整的分析流程"""
        print("开始荧光珠分辨率校准分析...")
        
        # 1. 加载图像
        print("1. 加载图像...")
        self.load_image()
        
        # 显示检测预览（如果需要）
        if show_preview:
            self.show_detection_preview(min_distance, threshold_percentile)
        
        # 2. 检测荧光珠
        print("2. 检测荧光珠...")
        threshold = np.percentile(self.image, threshold_percentile)
        self.detect_beads(min_distance=min_distance, threshold_abs=threshold, 
                         threshold_percentile=threshold_percentile, show_debug=True)
        
        if len(self.bead_positions) == 0:
            print("❌ 未检测到荧光珠！")
            print("建议:")
            print("1. 降低threshold_percentile (如85, 80)")
            print("2. 减小min_distance (如15, 10)")
            print("3. 检查图像路径和格式")
            print("4. 使用show_preview=True查看检测过程")
            return None
        
        # 3. 拟合所有荧光珠
        print("3. 进行二维高斯拟合...")
        self.fit_all_beads(roi_size=roi_size)
        
        if len(self.gaussian_params) == 0:
            print("❌ 未成功拟合任何荧光珠！")
            print("建议增大roi_size或检查荧光珠质量")
            return None
        
        # 4. 计算结果
        print("4. 计算半高面积...")
        results = self.calculate_average_fwhm_area()
        
        # 5. 显示结果
        print("\n=== 分析结果 ===")
        print(f"检测到荧光珠数量: {len(self.bead_positions)}")
        print(f"成功拟合荧光珠数量: {results['num_beads_fitted']}")
        print(f"像素尺寸: {results['pixel_size_um']:.4f} μm/像素")
        print(f"平均 FWHM X: {results['fwhm_x_um']:.3f} μm")
        print(f"平均 FWHM Y: {results['fwhm_y_um']:.3f} μm")
        print(f"二维高斯半高面积: {results['fwhm_area_um2']:.3f} μm²")
        print(f"等效直径: {results['equivalent_diameter_um']:.3f} μm")
        
        return results

    def extract_bead_roi(self, center: Tuple[int, int], roi_radius: int = 15) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        提取荧光珠周围的圆形ROI
        
        Args:
            center: 荧光珠中心坐标 (x, y)
            roi_radius: ROI半径(像素)
        
        Returns:
            roi_data: ROI内的强度数据
            x_coords: x坐标
            y_coords: y坐标
        """
        x_center, y_center = center
        
        # 创建圆形掩膜
        y, x = np.ogrid[:self.image.shape[0], :self.image.shape[1]]
        mask = (x - x_center)**2 + (y - y_center)**2 <= roi_radius**2
        
        # 获取ROI范围
        x_min = max(0, x_center - roi_radius)
        x_max = min(self.image.shape[1], x_center + roi_radius + 1)
        y_min = max(0, y_center - roi_radius)
        y_max = min(self.image.shape[0], y_center + roi_radius + 1)
        
        # 提取ROI区域
        roi_mask = mask[y_min:y_max, x_min:x_max]
        roi_data = self.image[y_min:y_max, x_min:x_max].copy()
        
        # 只保留圆形区域内的数据
        roi_data[~roi_mask] = 0
        
        # 创建坐标网格
        x_coords = np.arange(x_min, x_max)
        y_coords = np.arange(y_min, y_max)
        
        return roi_data, x_coords, y_coords
    
    def calculate_fwhm_area_direct(self, center: Tuple[int, int], roi_radius: int = 15) -> Dict:
        """
        直接计算荧光珠的半高面积（不使用拟合）
        
        Args:
            center: 荧光珠中心坐标
            roi_radius: ROI半径
        """
        roi_data, x_coords, y_coords = self.extract_bead_roi(center, roi_radius)
        
        if roi_data.size == 0:
            return None
        
        # 找到最大值和最小值
        max_intensity = np.max(roi_data)
        min_intensity = np.min(roi_data[roi_data > 0])  # 排除掩膜外的0值
        
        # 计算半高值
        half_max = (max_intensity + min_intensity) / 2
        
        # 找到所有大于等于半高值的像素
        fwhm_mask = roi_data >= half_max
        fwhm_pixels = np.sum(fwhm_mask)
        
        # 转换为物理面积
        fwhm_area_um2 = fwhm_pixels * (self.pixel_size_um ** 2)
        
        # 计算等效直径
        equivalent_diameter_um = 2 * np.sqrt(fwhm_area_um2 / np.pi)
        
        return {
            'max_intensity': max_intensity,
            'min_intensity': min_intensity,
            'half_max': half_max,
            'fwhm_pixels': fwhm_pixels,
            'fwhm_area_um2': fwhm_area_um2,
            'equivalent_diameter_um': equivalent_diameter_um,
            'roi_data': roi_data,
            'x_coords': x_coords,
            'y_coords': y_coords
        }
    
    def plot_bead_3d(self, center: Tuple[int, int], roi_radius: int = 15, save_path: str = None):
        """
        绘制单个荧光珠的3D山峰图
        
        Args:
            center: 荧光珠中心坐标
            roi_radius: ROI半径
            save_path: 保存路径
        """
        result = self.calculate_fwhm_area_direct(center, roi_radius)
        if result is None:
            print(f"无法分析荧光珠 {center}")
            return
        
        roi_data = result['roi_data']
        x_coords = result['x_coords']
        y_coords = result['y_coords']
        
        # 创建坐标网格
        X, Y = np.meshgrid(x_coords, y_coords)
        
        # 创建3D图
        fig = plt.figure(figsize=(15, 5))
        
        # 3D表面图
        ax1 = fig.add_subplot(131, projection='3d')
        surf = ax1.plot_surface(X, Y, roi_data, cmap='hot', alpha=0.8)
        
        # 添加半高平面
        half_max = result['half_max']
        half_plane = np.full_like(roi_data, half_max)
        half_plane[roi_data == 0] = 0
        ax1.plot_surface(X, Y, half_plane, alpha=0.3, color='blue')
        
        ax1.set_xlabel('X (pixels)')
        ax1.set_ylabel('Y (pixels)')
        ax1.set_zlabel('Intensity')
        ax1.set_title(f'3D Peak View\nCenter: {center}')
        
        # 2D热图
        ax2 = fig.add_subplot(132)
        im = ax2.imshow(roi_data, cmap='hot', origin='lower', 
                       extent=[x_coords[0], x_coords[-1], y_coords[0], y_coords[-1]])
        
        # 添加半高轮廓线
        contour = ax2.contour(X, Y, roi_data, levels=[half_max], colors='blue', linewidths=2)
        ax2.clabel(contour, fmt='Half Max')
        
        ax2.set_xlabel('X (pixels)')
        ax2.set_ylabel('Y (pixels)')
        ax2.set_title('2D Intensity Map')
        plt.colorbar(im, ax=ax2, label='Intensity')
        
        # 强度剖面图
        ax3 = fig.add_subplot(133)
        center_y_idx = len(y_coords) // 2
        if center_y_idx < roi_data.shape[0]:
            profile = roi_data[center_y_idx, :]
            ax3.plot(x_coords, profile, 'b-', linewidth=2, label='Intensity Profile')
            ax3.axhline(y=half_max, color='red', linestyle='--', label=f'Half Max ({half_max:.0f})')
            ax3.fill_between(x_coords, 0, profile, where=(profile >= half_max), 
                           alpha=0.3, color='green', label='FWHM Area')
        
        ax3.set_xlabel('X (pixels)')
        ax3.set_ylabel('Intensity')
        ax3.set_title('Center Line Profile')
        ax3.legend()
        ax3.grid(True)
        
        # 添加分析结果文本
        result_text = f"""Analysis Results:
Max Intensity: {result['max_intensity']:.0f}
Half Max: {result['half_max']:.0f}
FWHM Pixels: {result['fwhm_pixels']}
FWHM Area: {result['fwhm_area_um2']:.3f} μm²
Equiv. Diameter: {result['equivalent_diameter_um']:.3f} μm"""
        
        fig.text(0.02, 0.02, result_text, fontsize=10, fontfamily='monospace',
                bbox=dict(boxstyle="round,pad=0.3", facecolor="lightgray"))
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()
        
        return result
    
    def analyze_all_beads_direct(self, roi_radius: int = 15) -> List[Dict]:
        """直接分析所有荧光珠的半高面积"""
        if not self.bead_positions:
            raise ValueError("请先检测荧光珠位置")
        
        results = []
        
        for i, position in enumerate(self.bead_positions):
            print(f"分析荧光珠 {i+1}/{len(self.bead_positions)} at {position}")
            result = self.calculate_fwhm_area_direct(position, roi_radius)
            if result:
                result['position'] = position
                result['index'] = i
                results.append(result)
        
        print(f"成功分析 {len(results)} 个荧光珠")
        return results
    
    def calculate_average_fwhm_direct(self, roi_radius: int = 15) -> Dict:
        """计算所有荧光珠的平均半高面积（直接方法）"""
        results = self.analyze_all_beads_direct(roi_radius)
        
        if not results:
            raise ValueError("没有成功分析的荧光珠")
        
        # 提取所有面积数据
        fwhm_areas = [r['fwhm_area_um2'] for r in results]
        fwhm_pixels_list = [r['fwhm_pixels'] for r in results]
        equivalent_diameters = [r['equivalent_diameter_um'] for r in results]
        
        # 计算统计量
        avg_fwhm_area = np.mean(fwhm_areas)
        std_fwhm_area = np.std(fwhm_areas)
        avg_fwhm_pixels = np.mean(fwhm_pixels_list)
        avg_equivalent_diameter = np.mean(equivalent_diameters)
        
        summary = {
            'num_beads_analyzed': len(results),
            'avg_fwhm_area_um2': avg_fwhm_area,
            'std_fwhm_area_um2': std_fwhm_area,
            'avg_fwhm_pixels': avg_fwhm_pixels,
            'avg_equivalent_diameter_um': avg_equivalent_diameter,
            'individual_results': results,
            'roi_radius_pixels': roi_radius,
            'roi_radius_um': roi_radius * self.pixel_size_um,
            'pixel_size_um': self.pixel_size_um
        }
        
        return summary
    
    def visualize_all_beads_analysis(self, roi_radius: int = 15, save_path: str = None):
        """可视化所有荧光珠的分析结果"""
        summary = self.calculate_average_fwhm_direct(roi_radius)
        results = summary['individual_results']
        
        fig, axes = plt.subplots(2, 3, figsize=(18, 12))
        
        # 1. 原始图像和检测结果
        axes[0, 0].imshow(self.image, cmap='gray')
        for i, result in enumerate(results):
            pos = result['position']
            axes[0, 0].scatter(pos[0], pos[1], c='red', marker='+', s=100)
            axes[0, 0].text(pos[0]+2, pos[1]+2, str(i+1), color='yellow', fontsize=8)
            
            # 画ROI圆圈
            circle = plt.Circle(pos, roi_radius, fill=False, color='cyan', linewidth=1)
            axes[0, 0].add_patch(circle)
        
        axes[0, 0].set_title(f'Detected Beads with ROI (radius={roi_radius}px)')
        axes[0, 0].set_xlabel('X (pixels)')
        axes[0, 0].set_ylabel('Y (pixels)')
        
        # 2. FWHM面积分布
        areas = [r['fwhm_area_um2'] for r in results]
        axes[0, 1].hist(areas, bins=min(10, len(areas)), alpha=0.7, edgecolor='black')
        axes[0, 1].axvline(summary['avg_fwhm_area_um2'], color='red', linestyle='--', 
                          label=f"Mean: {summary['avg_fwhm_area_um2']:.3f}")
        axes[0, 1].set_xlabel('FWHM Area (μm²)')
        axes[0, 1].set_ylabel('Frequency')
        axes[0, 1].set_title('FWHM Area Distribution')
        axes[0, 1].legend()
        
        # 3. 等效直径分布
        diameters = [r['equivalent_diameter_um'] for r in results]
        axes[0, 2].hist(diameters, bins=min(10, len(diameters)), alpha=0.7, edgecolor='black')
        axes[0, 2].axvline(summary['avg_equivalent_diameter_um'], color='red', linestyle='--',
                          label=f"Mean: {summary['avg_equivalent_diameter_um']:.3f}")
        axes[0, 2].set_xlabel('Equivalent Diameter (μm)')
        axes[0, 2].set_ylabel('Frequency')
        axes[0, 2].set_title('Equivalent Diameter Distribution')
        axes[0, 2].legend()
        
        # 4. 面积vs位置散点图
        x_positions = [r['position'][0] for r in results]
        y_positions = [r['position'][1] for r in results]
        scatter = axes[1, 0].scatter(x_positions, y_positions, c=areas, 
                                   cmap='viridis', s=100, edgecolors='black')
        axes[1, 0].set_xlabel('X Position (pixels)')
        axes[1, 0].set_ylabel('Y Position (pixels)')
        axes[1, 0].set_title('FWHM Area vs Position')
        plt.colorbar(scatter, ax=axes[1, 0], label='FWHM Area (μm²)')
        
        # 5. 强度vs面积关系
        max_intensities = [r['max_intensity'] for r in results]
        axes[1, 1].scatter(max_intensities, areas, alpha=0.7, edgecolors='black')
        axes[1, 1].set_xlabel('Max Intensity')
        axes[1, 1].set_ylabel('FWHM Area (μm²)')
        axes[1, 1].set_title('Max Intensity vs FWHM Area')
        
        # 6. 统计摘要
        summary_text = f"""Analysis Summary:
Total beads analyzed: {summary['num_beads_analyzed']}
ROI radius: {roi_radius} pixels ({summary['roi_radius_um']:.2f} μm)
Pixel size: {summary['pixel_size_um']:.4f} μm/pixel

FWHM Area Statistics:
Mean: {summary['avg_fwhm_area_um2']:.3f} ± {summary['std_fwhm_area_um2']:.3f} μm²
Average pixels: {summary['avg_fwhm_pixels']:.1f}
Average diameter: {summary['avg_equivalent_diameter_um']:.3f} μm

Note: This is the actual half-maximum area 
calculated from intensity thresholding, not 
from Gaussian fitting."""
        
        axes[1, 2].text(0.1, 0.5, summary_text, transform=axes[1, 2].transAxes,
                        fontsize=10, verticalalignment='center', fontfamily='monospace')
        axes[1, 2].set_title('Analysis Summary')
        axes[1, 2].axis('off')
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()
        
        return summary

    def create_averaged_3d_peak(self, roi_radius: int = 15) -> Dict:
        """
        创建所有荧光珠的平均3D山峰图
        
        Args:
            roi_radius: ROI半径
        
        Returns:
            包含平均强度分布的字典
        """
        if not self.bead_positions:
            raise ValueError("请先检测荧光珠位置")
        
        # 收集所有有效的ROI数据
        all_roi_data = []
        valid_results = []
        
        for i, position in enumerate(self.bead_positions):
            result = self.calculate_fwhm_area_direct(position, roi_radius)
            if result and result['roi_data'].size > 0:
                roi_data = result['roi_data']
                # 确保ROI大小一致
                target_size = 2 * roi_radius + 1
                if roi_data.shape[0] == target_size and roi_data.shape[1] == target_size:
                    all_roi_data.append(roi_data)
                    valid_results.append(result)
        
        if not all_roi_data:
            raise ValueError("没有有效的ROI数据")
        
        # 计算平均强度分布
        avg_roi_data = np.mean(all_roi_data, axis=0)
        std_roi_data = np.std(all_roi_data, axis=0)
        
        # 计算平均的半高面积参数
        max_intensity = np.max(avg_roi_data)
        min_intensity = np.min(avg_roi_data[avg_roi_data > 0])
        half_max = (max_intensity + min_intensity) / 2
        
        # 计算平均半高面积
        fwhm_mask = avg_roi_data >= half_max
        fwhm_pixels = np.sum(fwhm_mask)
        fwhm_area_um2 = fwhm_pixels * (self.pixel_size_um ** 2)
        equivalent_diameter_um = 2 * np.sqrt(fwhm_area_um2 / np.pi)
        
        # 创建坐标
        center_offset = roi_radius
        x_coords = np.arange(-center_offset, center_offset + 1)
        y_coords = np.arange(-center_offset, center_offset + 1)
        
        return {
            'avg_roi_data': avg_roi_data,
            'std_roi_data': std_roi_data,
            'x_coords': x_coords,
            'y_coords': y_coords,
            'max_intensity': max_intensity,
            'min_intensity': min_intensity,
            'half_max': half_max,
            'fwhm_pixels': fwhm_pixels,
            'fwhm_area_um2': fwhm_area_um2,
            'equivalent_diameter_um': equivalent_diameter_um,
            'num_beads_averaged': len(all_roi_data),
            'individual_results': valid_results
        }
    
    def plot_averaged_3d_peak(self, roi_radius: int = 15, save_path: str = None):
        """
        绘制所有荧光珠的平均3D山峰图
        
        Args:
            roi_radius: ROI半径
            save_path: 保存路径
        """
        avg_result = self.create_averaged_3d_peak(roi_radius)
        
        avg_roi_data = avg_result['avg_roi_data']
        std_roi_data = avg_result['std_roi_data']
        x_coords = avg_result['x_coords']
        y_coords = avg_result['y_coords']
        half_max = avg_result['half_max']
        
        # 创建坐标网格（以像素为单位）
        X, Y = np.meshgrid(x_coords, y_coords)
        
        # 转换为物理坐标（微米）
        X_um = X * self.pixel_size_um
        Y_um = Y * self.pixel_size_um
        
        # 创建更大的图形
        fig = plt.figure(figsize=(20, 12))
        
        # 1. 主要的3D表面图
        ax1 = fig.add_subplot(2, 3, 1, projection='3d')
        surf = ax1.plot_surface(X_um, Y_um, avg_roi_data, cmap='hot', alpha=0.8, 
                               linewidth=0, antialiased=True)
        
        # 添加半高平面
        half_plane = np.full_like(avg_roi_data, half_max)
        ax1.plot_surface(X_um, Y_um, half_plane, alpha=0.3, color='blue')
        
        ax1.set_xlabel('X (μm)')
        ax1.set_ylabel('Y (μm)')
        ax1.set_zlabel('Average Intensity')
        ax1.set_title(f'Average 3D Peak\n({avg_result["num_beads_averaged"]} beads)')
        
        # 2. 2D热图
        ax2 = fig.add_subplot(2, 3, 2)
        extent = [X_um.min(), X_um.max(), Y_um.min(), Y_um.max()]
        im = ax2.imshow(avg_roi_data, cmap='hot', origin='lower', extent=extent)
        
        # 添加半高轮廓线
        contour = ax2.contour(X_um, Y_um, avg_roi_data, levels=[half_max], 
                             colors='blue', linewidths=2)
        ax2.clabel(contour, fmt='Half Max')
        
        ax2.set_xlabel('X (μm)')
        ax2.set_ylabel('Y (μm)')
        ax2.set_title('Average 2D Intensity Map')
        plt.colorbar(im, ax=ax2, label='Average Intensity')
        
        # 3. 中心线剖面图
        ax3 = fig.add_subplot(2, 3, 3)
        center_idx = len(y_coords) // 2
        profile = avg_roi_data[center_idx, :]
        profile_std = std_roi_data[center_idx, :]
        
        x_um_1d = x_coords * self.pixel_size_um
        ax3.plot(x_um_1d, profile, 'b-', linewidth=2, label='Average Profile')
        ax3.fill_between(x_um_1d, profile - profile_std, profile + profile_std, 
                        alpha=0.3, color='blue', label='±1 STD')
        ax3.axhline(y=half_max, color='red', linestyle='--', 
                   label=f'Half Max ({half_max:.0f})')
        ax3.fill_between(x_um_1d, 0, profile, where=(profile >= half_max), 
                        alpha=0.3, color='green', label='FWHM Area')
        
        ax3.set_xlabel('X (μm)')
        ax3.set_ylabel('Average Intensity')
        ax3.set_title('Center Line Profile')
        ax3.legend()
        ax3.grid(True)
        
        # 4. 标准差图
        ax4 = fig.add_subplot(2, 3, 4)
        im_std = ax4.imshow(std_roi_data, cmap='viridis', origin='lower', extent=extent)
        ax4.set_xlabel('X (μm)')
        ax4.set_ylabel('Y (μm)')
        ax4.set_title('Standard Deviation Map')
        plt.colorbar(im_std, ax=ax4, label='Intensity STD')
        
        # 5. 径向剖面图
        ax5 = fig.add_subplot(2, 3, 5)
        center_x, center_y = len(x_coords) // 2, len(y_coords) // 2
        
        # 计算径向距离
        Y_grid, X_grid = np.meshgrid(np.arange(avg_roi_data.shape[0]), 
                                    np.arange(avg_roi_data.shape[1]), indexing='ij')
        radial_distance = np.sqrt((X_grid - center_x)**2 + (Y_grid - center_y)**2)
        
        # 创建径向剖面
        max_radius = min(center_x, center_y)
        radial_bins = np.arange(0, max_radius + 1)
        radial_profile = []
        radial_std = []
        
        for r in radial_bins:
            mask = (radial_distance >= r - 0.5) & (radial_distance < r + 0.5)
            if np.any(mask):
                radial_profile.append(np.mean(avg_roi_data[mask]))
                radial_std.append(np.std(avg_roi_data[mask]))
            else:
                radial_profile.append(0)
                radial_std.append(0)
        
        radial_distance_um = radial_bins * self.pixel_size_um
        ax5.plot(radial_distance_um, radial_profile, 'b-', linewidth=2, label='Radial Profile')
        ax5.fill_between(radial_distance_um, 
                        np.array(radial_profile) - np.array(radial_std),
                        np.array(radial_profile) + np.array(radial_std),
                        alpha=0.3, color='blue', label='±1 STD')
        ax5.axhline(y=half_max, color='red', linestyle='--', label='Half Max')
        ax5.set_xlabel('Radial Distance (μm)')
        ax5.set_ylabel('Average Intensity')
        ax5.set_title('Radial Profile')
        ax5.legend()
        ax5.grid(True)
        
        # 6. 统计摘要
        summary_text = f"""Average Bead Analysis:
Number of beads: {avg_result['num_beads_averaged']}
ROI radius: {roi_radius} pixels ({roi_radius * self.pixel_size_um:.2f} μm)
Pixel size: {self.pixel_size_um:.4f} μm/pixel

Intensity Statistics:
Max intensity: {avg_result['max_intensity']:.1f}
Min intensity: {avg_result['min_intensity']:.1f}
Half max: {avg_result['half_max']:.1f}

FWHM Measurements:
FWHM pixels: {avg_result['fwhm_pixels']}
FWHM area: {avg_result['fwhm_area_um2']:.3f} μm²
Equivalent diameter: {avg_result['equivalent_diameter_um']:.3f} μm

Physical dimensions:
Total ROI: {(2*roi_radius+1)*self.pixel_size_um:.2f} × {(2*roi_radius+1)*self.pixel_size_um:.2f} μm²
"""
        
        ax6 = fig.add_subplot(2, 3, 6)
        ax6.text(0.1, 0.5, summary_text, transform=ax6.transAxes,
                fontsize=10, verticalalignment='center', fontfamily='monospace')
        ax6.set_title('Analysis Summary')
        ax6.axis('off')
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()
        
        return avg_result

    def run_direct_analysis(self, min_distance: int = 50, roi_radius: int = 30, 
                          threshold_percentile: float = 85, show_preview: bool = False) -> Dict:
        """运行直接分析流程（不使用高斯拟合）"""
        print("开始荧光珠直接半高面积分析...")
        
        # 1. 加载图像
        print("1. 加载图像...")
        self.load_image()
        
        # 显示检测预览
        if show_preview:
            self.show_detection_preview(min_distance, threshold_percentile)
        
        # 2. 检测荧光珠
        print("2. 检测荧光珠...")
        threshold = np.percentile(self.image, threshold_percentile)
        self.detect_beads(min_distance=min_distance, threshold_abs=threshold, 
                         threshold_percentile=threshold_percentile, show_debug=True)
        
        if len(self.bead_positions) == 0:
            print("❌ 未检测到荧光珠！")
            return None
        
        # 3. 直接计算半高面积
        print("3. 计算半高面积...")
        summary = self.calculate_average_fwhm_direct(roi_radius)
        
        # 4. 显示结果
        print("\n=== 直接分析结果 ===")
        print(f"检测到荧光珠数量: {len(self.bead_positions)}")
        print(f"成功分析荧光珠数量: {summary['num_beads_analyzed']}")
        print(f"ROI半径: {roi_radius} 像素 ({summary['roi_radius_um']:.2f} μm)")
        print(f"最小检测距离: {min_distance} 像素 ({min_distance * self.pixel_size_um:.2f} μm)")
        print(f"像素尺寸: {summary['pixel_size_um']:.4f} μm/像素")
        print(f"平均半高面积: {summary['avg_fwhm_area_um2']:.3f} ± {summary['std_fwhm_area_um2']:.3f} μm²")
        print(f"平均等效直径: {summary['avg_equivalent_diameter_um']:.3f} μm")
        
        return summary

def main():
    """主函数示例"""
    image_path = "D:\code\Lissajous_scan_git\Lissajous_sacn\FOV_test_data\FOV_ybmsy\\102um\AVG_fig_beads_phase_8_357_png.png"
    
    calibrator = FluorescentBeadCalibration(
        image_path=image_path,
        physical_size_um=102,
        image_size_px=512
    )
    
    try:
        # 运行直接分析 - 调整参数避免重复检测
        summary = calibrator.run_direct_analysis(
            min_distance=50,      # 增加最小距离，约2.1微米，避免重复检测
            roi_radius=10,        # 增加ROI半径，约1.5微米，覆盖整个荧光珠
            threshold_percentile=80,  # 较低阈值确保检测到边缘的珠子
            show_preview=True
        )
        
        if summary:
            # 可视化所有结果
            calibrator.visualize_all_beads_analysis(
                roi_radius=18,
                save_path="direct_analysis_results.png"
            )
            
            # 创建平均3D山峰图
            print("\n创建所有荧光珠的平均3D山峰图...")
            avg_result = calibrator.plot_averaged_3d_peak(
                roi_radius=18,
                save_path="averaged_3d_peak.png"
            )
            
            # 显示几个代表性荧光珠的3D图
            print("\n显示前3个荧光珠的单独3D山峰图...")
            for i in range(min(3, len(calibrator.bead_positions))):
                center = calibrator.bead_positions[i]
                calibrator.plot_bead_3d(center, roi_radius=18, 
                                      save_path=f"bead_{i+1}_3d.png")
            
            # 打印更详细的统计信息
            print(f"\n=== 详细统计信息 ===")
            individual_areas = [r['fwhm_area_um2'] for r in summary['individual_results']]
            print(f"各荧光珠半高面积 (μm²): {[f'{area:.3f}' for area in individual_areas]}")
            print(f"面积范围: {min(individual_areas):.3f} - {max(individual_areas):.3f} μm²")
            print(f"变异系数: {(summary['std_fwhm_area_um2']/summary['avg_fwhm_area_um2']*100):.1f}%")
        
        return summary
        
    except Exception as e:
        print(f"分析失败: {e}")
        return None

if __name__ == "__main__":
    main()
