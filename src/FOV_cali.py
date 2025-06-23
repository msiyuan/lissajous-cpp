# import numpy as np
# from PIL import Image
# from scipy.optimize import curve_fit
# from scipy.signal import find_peaks
# import matplotlib.pyplot as plt
# from skimage.filters import gaussian
# from skimage.measure import label, regionprops
# from skimage.morphology import binary_opening, binary_closing, disk # 导入形态学操作

# def load_16bit_png(image_path):
#     """
#     加载16位PNG图像。
#     Args:
#         image_path (str): 图像文件的路径。
#     Returns:
#         numpy.ndarray: 图像数据，转换为float类型。
#     """
#     try:
#         img = Image.open(image_path)
#         if img.mode != 'I;16': # 'I;16' is the mode for 16-bit grayscale
#             print(f"Warning: Image mode is {img.mode}, converting to 16-bit grayscale if possible.")
#             img = img.convert('I;16')
        
#         img_array = np.array(img, dtype=np.float32)
#         print(f"Image loaded with shape: {img_array.shape}, dtype: {img_array.dtype}")
#         return img_array
#     except Exception as e:
#         print(f"Error loading image: {e}")
#         return None

# def gaussian_function(x, A, mu, sigma, B):
#     """
#     高斯函数模型。
#     Args:
#         x (numpy.ndarray): 位置数组。
#         A (float): 峰值强度。
#         mu (float): 峰值中心位置。
#         sigma (float): 标准差。
#         B (float): 基线强度。
#     Returns:
#         numpy.ndarray: 在给定位置x处的函数值。
#     """
#     return A * np.exp(-(x - mu)**2 / (2 * sigma**2)) + B

# def calculate_fwhm(sigma):
#     """
#     根据高斯拟合的标准差计算FWHM。
#     Args:
#         sigma (float): 高斯拟合的标准差。
#     Returns:
#         float: 全宽半高 (FWHM)。
#     """
#     return 2 * np.sqrt(2 * np.log(2)) * sigma

# def process_bead(bead_image_segment, pixel_resolution_um):
#     """
#     处理单个荧光微珠图像段，进行高斯拟合并计算FWHM。
#     Args:
#         bead_image_segment (numpy.ndarray): 包含单个微珠的图像片段。
#         pixel_resolution_um (float): 每个像素对应的微米数。
#     Returns:
#         float: 该微珠的横向分辨率 (FWHM)，单位微米。
#         tuple: (x_profile, y_profile, x_fit, y_fit) 用于可视化。
#     """
#     height, width = bead_image_segment.shape
    
#     # 提取中心行和中心列的强度剖面
#     x_profile_data = bead_image_segment[height // 2, :]
#     y_profile_data = bead_image_segment[:, width // 2]

#     # 为了更好的拟合，可以对强度剖面进行平滑处理
#     x_profile_data_smoothed = gaussian(x_profile_data, sigma=1)
#     y_profile_data_smoothed = gaussian(y_profile_data, sigma=1)
    
#     # 获取位置数组
#     x_positions = np.arange(width)
#     y_positions = np.arange(height)

#     fwhm_x_um = None
#     fwhm_y_um = None
#     x_fit_curve = None
#     y_fit_curve = None

#     # X轴高斯拟合
#     try:
#         # 尝试猜测初始参数: 峰值强度, 峰值中心, 标准差, 基线
#         initial_guess_x = [np.max(x_profile_data_smoothed) - np.min(x_profile_data_smoothed), 
#                            np.argmax(x_profile_data_smoothed), 
#                            width / 6, 
#                            np.min(x_profile_data_smoothed)]
#         # 增加bounds以限制sigma为正数，并使mu在合理的范围内
#         bounds_x = ([0, 0, 0.1, -np.inf], [np.inf, width, width/2, np.inf])
#         popt_x, pcov_x = curve_fit(gaussian_function, x_positions, x_profile_data_smoothed, p0=initial_guess_x, bounds=bounds_x, maxfev=5000)
#         A_x, mu_x, sigma_x, B_x = popt_x
#         fwhm_x_pixels = calculate_fwhm(sigma_x)
#         fwhm_x_um = fwhm_x_pixels * pixel_resolution_um
#         x_fit_curve = gaussian_function(x_positions, *popt_x)
#     except Exception as e:
#         print(f"Error fitting X-axis Gaussian: {e}")

#     # Y轴高斯拟合
#     try:
#         initial_guess_y = [np.max(y_profile_data_smoothed) - np.min(y_profile_data_smoothed), 
#                            np.argmax(y_profile_data_smoothed), 
#                            height / 6, 
#                            np.min(y_profile_data_smoothed)]
#         bounds_y = ([0, 0, 0.1, -np.inf], [np.inf, height, height/2, np.inf])
#         popt_y, pcov_y = curve_fit(gaussian_function, y_positions, y_profile_data_smoothed, p0=initial_guess_y, bounds=bounds_y, maxfev=5000)
#         A_y, mu_y, sigma_y, B_y = popt_y
#         fwhm_y_pixels = calculate_fwhm(sigma_y)
#         fwhm_y_um = fwhm_y_pixels * pixel_resolution_um
#         y_fit_curve = gaussian_function(y_positions, *popt_y)
#     except Exception as e:
#         print(f"Error fitting Y-axis Gaussian: {e}")

#     # 返回平均FWHM（如果两者都成功）
#     if fwhm_x_um is not None and fwhm_y_um is not None:
#         return (fwhm_x_um + fwhm_y_um) / 2, (x_profile_data, y_profile_data, x_fit_curve, y_fit_curve, x_positions, y_positions)
#     elif fwhm_x_um is not None:
#         return fwhm_x_um, (x_profile_data, y_profile_data, x_fit_curve, y_fit_curve, x_positions, y_positions)
#     elif fwhm_y_um is not None:
#         return fwhm_y_um, (x_profile_data, y_profile_data, x_fit_curve, y_fit_curve, x_positions, y_positions)
#     else:
#         return None, (x_profile_data, y_profile_data, None, None, x_positions, y_positions)


# def main(image_path, fov_um=(27, 27), min_bead_intensity_threshold_ratio=0.3, bead_min_area=20, bead_max_area=1000, plot_results=True):
#     """
#     主函数，用于加载图像，识别微珠，计算横向分辨率。
#     Args:
#         image_path (str): 图像文件的路径。
#         fov_um (tuple): 图像的物理尺寸 (FOV)，格式为 (宽度_微米, 高度_微米)。
#                         论文中是 140x140 µm。
#         min_bead_intensity_threshold_ratio (float): 用于微珠分割的最小强度阈值比例
#                                                     (相对于图像最大强度的比例)。
#         bead_min_area (int): 识别的微珠的最小像素面积。
#         bead_max_area (int): 识别的微珠的最大像素面积。
#         plot_results (bool): 是否绘制结果图。
#     """
#     image_array = load_16bit_png(image_path)
#     if image_array is None:
#         return

#     height, width = image_array.shape
    
#     # 计算像素分辨率（µm/pixel）
#     pixel_resolution_x = fov_um[0] / width
#     pixel_resolution_y = fov_um[1] / height
#     pixel_resolution_um = (pixel_resolution_x + pixel_resolution_y) / 2 # 取平均值

#     print(f"Image dimensions: {width}x{height} pixels")
#     print(f"Calculated pixel resolution: {pixel_resolution_x:.3f} µm/pixel (X), {pixel_resolution_y:.3f} µm/pixel (Y)")
#     print(f"Average pixel resolution: {pixel_resolution_um:.3f} µm/pixel")

#     # --- 图像预处理 ---
#     # 应用高斯平滑以减少噪声，有助于微珠识别
#     smoothed_image = gaussian(image_array, sigma=1)

#     # --- 微珠识别和定位 ---
#     # 动态阈值：取平滑图像最大值的一定比例作为阈值
#     # 可以尝试使用 Otsu 阈值，它会自动找到一个好的全局阈值
#     # from skimage.filters import threshold_otsu
#     # threshold_value = threshold_otsu(smoothed_image)
#     threshold_value = np.max(smoothed_image) * min_bead_intensity_threshold_ratio
#     binary_image = smoothed_image > threshold_value
    
#     # 形态学操作：开运算可以去除小的噪声点，闭运算可以连接小的断裂和填充小孔
#     # 根据微珠大小和噪声情况调整 `disk` 的半径
#     selem = disk(1) # 结构元素，例如半径为1的圆盘
#     binary_image = binary_opening(binary_image, selem)
#     binary_image = binary_closing(binary_image, selem)
    
#     # 连通组件分析
#     labeled_image = label(binary_image)
#     regions = regionprops(labeled_image)

#     selected_beads_fwhm = []
#     bead_segments_for_plot = []

#     print(f"\nFound {len(regions)} potential regions.")
    
#     # 筛选合适的微珠
#     for i, region in enumerate(regions):
#         # 打印每个区域的面积和长宽比，帮助调整参数
#         # print(f"Region {i+1}: Area = {region.area} pixels, Aspect Ratio = {region.major_axis_length / region.minor_axis_length if region.minor_axis_length > 0 else 0:.2f}")

#         # 添加对形状的初步筛选（例如，长宽比）
#         aspect_ratio = region.major_axis_length / region.minor_axis_length if region.minor_axis_length > 0 else 0
        
#         # 调整这些条件以适应您的非圆形微珠，可以放宽长宽比要求
#         if bead_min_area < region.area < bead_max_area and 1.0 <= aspect_ratio <= 3.0: # 允许长宽比达到3，根据实际情况调整
#             # 提取微珠区域（考虑边界，防止截取到不完整的微珠）
#             min_row, min_col, max_row, max_col = region.bbox
#             # 扩展边界，确保包含整个微珠及周围背景，以便拟合
#             padding = 15 # 像素，适当增加填充
#             min_row_padded = max(0, min_row - padding)
#             min_col_padded = max(0, min_col - padding)
#             max_row_padded = min(height, max_row + padding)
#             max_col_padded = min(width, max_col + padding)

#             bead_segment = image_array[min_row_padded:max_row_padded, 
#                                        min_col_padded:max_col_padded]
            
#             # 确保微珠片段有足够的大小进行剖面提取和拟合
#             # 最小尺寸增加，因为非圆形可能需要更大的片段来捕捉其分布
#             if bead_segment.shape[0] > 10 and bead_segment.shape[1] > 10: 
#                 fwhm_um, plot_data = process_bead(bead_segment, pixel_resolution_um)
#                 if fwhm_um is not None:
#                     selected_beads_fwhm.append(fwhm_um)
#                     bead_segments_for_plot.append({
#                         'segment': bead_segment,
#                         'bbox': region.bbox,
#                         'fwhm': fwhm_um,
#                         'plot_data': plot_data
#                     })
#                     print(f"Processed bead {i+1} (area: {region.area} pixels, aspect_ratio: {aspect_ratio:.2f}), FWHM: {fwhm_um:.3f} µm")
#             else:
#                 print(f"Skipping bead {i+1} (area: {region.area}) due to small segment size: {bead_segment.shape}")
#         else:
#             print(f"Skipping bead {i+1} (area: {region.area}, aspect_ratio: {aspect_ratio:.2f}) - did not meet criteria.")

#     if len(selected_beads_fwhm) > 0:
#         average_fwhm = np.mean(selected_beads_fwhm)
#         std_fwhm = np.std(selected_beads_fwhm)
#         print(f"\n--- Results ---")
#         print(f"Number of beads analyzed: {len(selected_beads_fwhm)}")
#         print(f"Average Lateral Resolution (FWHM): {average_fwhm:.3f} µm ± {std_fwhm:.3f} µm")
#     else:
#         print("\nNo suitable beads found or processed for FWHM calculation.")
#         # 在没有找到微珠时显示二进制图像，便于调试
#         if plot_results and image_array is not None:
#             plt.figure(figsize=(10, 5))
#             plt.subplot(1, 2, 1)
#             plt.imshow(image_array, cmap='gray')
#             plt.title('Original Image')
#             plt.axis('off')
            
#             plt.subplot(1, 2, 2)
#             plt.imshow(binary_image, cmap='gray')
#             plt.title(f'Binary Image (Threshold: {threshold_value:.2f})')
#             plt.axis('off')
#             plt.show()
#         return

#     # --- 可视化 ---
#     if plot_results:
#         plt.figure(figsize=(15, 10))

#         # 原始图像和识别的微珠
#         ax1 = plt.subplot(2, 2, 1)
#         ax1.imshow(image_array, cmap='gray')
#         ax1.set_title('Original Image with Identified Beads')
#         ax1.axis('off')
        
#         # 绘制识别出的微珠的边界框
#         for region in regions:
#             aspect_ratio = region.major_axis_length / region.minor_axis_length if region.minor_axis_length > 0 else 0
#             if bead_min_area < region.area < bead_max_area and 1.0 <= aspect_ratio <= 3.0:
#                 min_row, min_col, max_row, max_col = region.bbox
#                 rect = plt.Rectangle((min_col, min_row), max_col - min_col, max_row - min_row,
#                                      fill=False, edgecolor='red', linewidth=1)
#                 ax1.add_patch(rect)

#         # 示例微珠的强度剖面和高斯拟合
#         if len(bead_segments_for_plot) > 0:
#             # 选择一个微珠进行详细展示，例如第一个或面积最大的
#             display_bead_info = bead_segments_for_plot[0] 
            
#             ax2 = plt.subplot(2, 2, 2)
#             ax2.imshow(display_bead_info['segment'], cmap='gray')
#             ax2.set_title(f"Selected Bead (FWHM: {display_bead_info['fwhm']:.3f} µm)")
#             ax2.axis('off')

#             x_profile_data, y_profile_data, x_fit_curve, y_fit_curve, x_positions, y_positions = display_bead_info['plot_data']

#             ax3 = plt.subplot(2, 2, 3)
#             ax3.plot(x_positions * pixel_resolution_um, x_profile_data, 'b-', label='X-axis Data')
#             if x_fit_curve is not None:
#                 ax3.plot(x_positions * pixel_resolution_um, x_fit_curve, 'r--', label='X-axis Gaussian Fit')
#             ax3.set_title('X-axis Intensity Profile and Fit')
#             ax3.set_xlabel('Lateral position (µm)')
#             ax3.set_ylabel('Normalized intensity (a.u.)')
#             ax3.legend()

#             ax4 = plt.subplot(2, 2, 4)
#             ax4.plot(y_positions * pixel_resolution_um, y_profile_data, 'b-', label='Y-axis Data')
#             if y_fit_curve is not None:
#                 ax4.plot(y_positions * pixel_resolution_um, y_fit_curve, 'g--', label='Y-axis Gaussian Fit')
#             ax4.set_title('Y-axis Intensity Profile and Fit')
#             ax4.set_xlabel('Lateral position (µm)')
#             ax4.set_ylabel('Normalized intensity (a.u.)')
#             ax4.legend()

#         plt.tight_layout()
#         plt.show()

# # --- 使用示例 ---
# if __name__ == "__main__":
#     image_file = 'E:\code\\3-VS_proj\qt_proj\Lissajous_scan\imgsFOV\\frame_1750405833442.png' 
    
#     # 设定图像的实际物理FOV为 27 µm x 27 µm
#     image_fov_um = (27, 27) 

#     # 针对非圆形微珠的参数调整建议：
#     # 1. 降低 min_bead_intensity_threshold_ratio：如果微珠对比度不高，可能需要更低的阈值来包含它们。
#     # 2. 调整 bead_min_area 和 bead_max_area：根据实际微珠的像素大小进行调整。
#     # 3. 增加 padding：确保裁剪出的微珠区域足够大，以便捕捉非圆形形状的完整强度分布。
#     # 4. 调整形态学操作的结构元素半径：`selem = disk(radius)`，`radius` 根据微珠的连接和孔洞情况调整。
#     # 5. 放宽 aspect_ratio 的筛选范围（已在代码中实现，初始设置为 <= 3.0）。
#     main(
#         image_file, 
#         fov_um=image_fov_um,
#         min_bead_intensity_threshold_ratio=0.9, # 尝试降低阈值，例如从0.5到0.2或0.1
#         bead_min_area=15, # 根据实际微珠大小调整，例如从10增加到15
#         bead_max_area=1500, # 允许更大的微珠，防止连接的微珠被排除
#         plot_results=True
#     )



import numpy as np
from PIL import Image
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt
from skimage.filters import gaussian
from skimage.measure import label, regionprops
from skimage.morphology import binary_opening, binary_closing, disk

# 定义一个全局变量来存储选定的区域
selected_region_bbox = None

def load_16bit_png(image_path):
    """
    加载16位PNG图像。
    Args:
        image_path (str): 图像文件的路径。
    Returns:
        numpy.ndarray: 图像数据，转换为float类型。
    """
    try:
        img = Image.open(image_path)
        if img.mode != 'I;16': # 'I;16' is the mode for 16-bit grayscale
            print(f"Warning: Image mode is {img.mode}, converting to 16-bit grayscale if possible.")
            img = img.convert('I;16')
        
        img_array = np.array(img, dtype=np.float32)
        print(f"Image loaded with shape: {img_array.shape}, dtype: {img_array.dtype}")
        return img_array
    except Exception as e:
        print(f"Error loading image: {e}")
        return None

def gaussian_function(x, A, mu, sigma, B):
    """
    高斯函数模型。
    Args:
        x (numpy.ndarray): 位置数组。
        A (float): 峰值强度。
        mu (float): 峰值中心位置。
        sigma (float): 标准差。
        B (float): 基线强度。
    Returns:
        numpy.ndarray: 在给定位置x处的函数值。
    """
    return A * np.exp(-(x - mu)**2 / (2 * sigma**2)) + B

def calculate_fwhm(sigma):
    """
    根据高斯拟合的标准差计算FWHM。
    Args:
        sigma (float): 高斯拟合的标准差。
    Returns:
        float: 全宽半高 (FWHM)。
    """
    return 2 * np.sqrt(2 * np.log(2)) * sigma

def process_bead(bead_image_segment, pixel_resolution_um):
    """
    处理单个荧光微珠图像段，进行高斯拟合并计算FWHM。
    Args:
        bead_image_segment (numpy.ndarray): 包含单个微珠的图像片段。
        pixel_resolution_um (float): 每个像素对应的微米数。
    Returns:
        float: 该微珠的横向分辨率 (FWHM)，单位微米。
        tuple: (x_profile, y_profile, x_fit, y_fit) 用于可视化。
    """
    height, width = bead_image_segment.shape
    
    # 提取中心行和中心列的强度剖面
    x_profile_data = bead_image_segment[height // 2, :]
    y_profile_data = bead_image_segment[:, width // 2]

    # 为了更好的拟合，可以对强度剖面进行平滑处理
    x_profile_data_smoothed = gaussian(x_profile_data, sigma=1)
    y_profile_data_smoothed = gaussian(y_profile_data, sigma=1)
    
    # 获取位置数组
    x_positions = np.arange(width)
    y_positions = np.arange(height)

    fwhm_x_um = None
    fwhm_y_um = None
    x_fit_curve = None
    y_fit_curve = None

    # X轴高斯拟合
    try:
        # 尝试猜测初始参数: 峰值强度, 峰值中心, 标准差, 基线
        initial_guess_x = [np.max(x_profile_data_smoothed) - np.min(x_profile_data_smoothed), 
                           np.argmax(x_profile_data_smoothed), 
                           width / 6, 
                           np.min(x_profile_data_smoothed)]
        # 增加bounds以限制sigma为正数，并使mu在合理的范围内
        bounds_x = ([0, 0, 0.1, -np.inf], [np.inf, width, width/2, np.inf])
        popt_x, pcov_x = curve_fit(gaussian_function, x_positions, x_profile_data_smoothed, p0=initial_guess_x, bounds=bounds_x, maxfev=5000)
        A_x, mu_x, sigma_x, B_x = popt_x
        fwhm_x_pixels = calculate_fwhm(sigma_x)
        fwhm_x_um = fwhm_x_pixels * pixel_resolution_um
        x_fit_curve = gaussian_function(x_positions, *popt_x)
    except Exception as e:
        print(f"Error fitting X-axis Gaussian: {e}")

    # Y轴高斯拟合
    try:
        initial_guess_y = [np.max(y_profile_data_smoothed) - np.min(y_profile_data_smoothed), 
                           np.argmax(y_profile_data_smoothed), 
                           height / 6, 
                           np.min(y_profile_data_smoothed)]
        bounds_y = ([0, 0, 0.1, -np.inf], [np.inf, height, height/2, np.inf])
        popt_y, pcov_y = curve_fit(gaussian_function, y_positions, y_profile_data_smoothed, p0=initial_guess_y, bounds=bounds_y, maxfev=5000)
        A_y, mu_y, sigma_y, B_y = popt_y
        fwhm_y_pixels = calculate_fwhm(sigma_y)
        fwhm_y_um = fwhm_y_pixels * pixel_resolution_um
        y_fit_curve = gaussian_function(y_positions, *popt_y)
    except Exception as e:
        print(f"Error fitting Y-axis Gaussian: {e}")

    # 返回平均FWHM（如果两者都成功）
    if fwhm_x_um is not None and fwhm_y_um is not None:
        return (fwhm_x_um + fwhm_y_um) / 2, (x_profile_data, y_profile_data, x_fit_curve, y_fit_curve, x_positions, y_positions)
    elif fwhm_x_um is not None:
        return fwhm_x_um, (x_profile_data, y_profile_data, x_fit_curve, y_fit_curve, x_positions, y_positions)
    elif fwhm_y_um is not None:
        return fwhm_y_um, (x_profile_data, y_profile_data, x_fit_curve, y_fit_curve, x_positions, y_positions)
    else:
        return None, (x_profile_data, y_profile_data, None, None, x_positions, y_positions)

# --- 鼠标事件处理函数 ---
start_x, start_y = -1, -1
rect = None
ax_plot = None

def on_mouse_press(event):
    global start_x, start_y, rect, ax_plot, selected_region_bbox
    if event.inaxes != ax_plot: return
    
    start_x, start_y = event.xdata, event.ydata
    rect = plt.Rectangle((start_x, start_y), 0, 0, fill=False, edgecolor='red', linewidth=2)
    ax_plot.add_patch(rect)
    plt.draw()

def on_mouse_drag(event):
    global start_x, start_y, rect, ax_plot
    if event.inaxes != ax_plot: return

    cur_x, cur_y = event.xdata, event.ydata
    if rect:
        rect.set_width(cur_x - start_x)
        rect.set_height(cur_y - start_y)
        plt.draw()

def on_mouse_release(event):
    global start_x, start_y, rect, ax_plot, selected_region_bbox
    if event.inaxes != ax_plot: return

    end_x, end_y = event.xdata, event.ydata
    
    # 确保坐标是整数并按小到大排列
    x_min = int(min(start_x, end_x))
    x_max = int(max(start_x, end_x))
    y_min = int(min(start_y, end_y))
    y_max = int(max(start_y, end_y))

    selected_region_bbox = (y_min, x_min, y_max, x_max) # 格式为 (min_row, min_col, max_row, max_col)
    print(f"Selected region (bbox): {selected_region_bbox}")
    
    # 清除选择框并关闭图形，以便主程序继续
    if rect:
        rect.remove()
        rect = None
    plt.close(event.canvas.figure) # 关闭图形，这会让主程序从 plt.show() 返回


def main(image_path, fov_um=(27, 27), plot_results=True, manual_selection=True):
    """
    主函数，用于加载图像，识别微珠，计算横向分辨率。
    Args:
        image_path (str): 图像文件的路径。
        fov_um (tuple): 图像的物理尺寸 (FOV)，格式为 (宽度_微米, 高度_微米)。
        plot_results (bool): 是否绘制结果图。
        manual_selection (bool): 是否启用手动选择微珠区域。
    """
    image_array = load_16bit_png(image_path)
    if image_array is None:
        return

    height, width = image_array.shape
    
    # 计算像素分辨率（µm/pixel）
    pixel_resolution_x = fov_um[0] / width
    pixel_resolution_y = fov_um[1] / height
    pixel_resolution_um = (pixel_resolution_x + pixel_resolution_y) / 2 # 取平均值

    print(f"Image dimensions: {width}x{height} pixels")
    print(f"Calculated pixel resolution: {pixel_resolution_x:.3f} µm/pixel (X), {pixel_resolution_y:.3f} µm/pixel (Y)")
    print(f"Average pixel resolution: {pixel_resolution_um:.3f} µm/pixel")

    selected_regions_for_processing = []

    if manual_selection:
        global ax_plot, selected_region_bbox
        selected_region_bbox = None # 重置全局变量

        fig, ax_plot = plt.subplots(figsize=(8, 8))
        ax_plot.imshow(image_array, cmap='gray')
        ax_plot.set_title("Click and drag to select a bead region, then release. Close window to continue.")
        ax_plot.axis('image') # 保持图像比例
        
        # 连接鼠标事件
        fig.canvas.mpl_connect('button_press_event', on_mouse_press)
        fig.canvas.mpl_connect('motion_notify_event', on_mouse_drag)
        fig.canvas.mpl_connect('button_release_event', on_mouse_release)
        
        plt.show() # 显示图像并等待用户选择

        if selected_region_bbox:
            min_row, min_col, max_row, max_col = selected_region_bbox
            # 确保选择的区域有效
            if max_row > min_row and max_col > min_col:
                # 裁剪选定区域，不加额外 padding，因为用户已手动选择
                bead_segment = image_array[min_row:max_row, min_col:max_col]
                
                # 确保微珠片段有足够的大小进行剖面提取和拟合
                if bead_segment.shape[0] > 10 and bead_segment.shape[1] > 10: 
                    selected_regions_for_processing.append({
                        'segment': bead_segment,
                        'bbox': selected_region_bbox,
                        'source': 'manual'
                    })
                    print(f"Manually selected 1 region for processing.")
                else:
                    print(f"Manually selected region is too small: {bead_segment.shape}. Skipping.")
            else:
                print("Invalid region selected (width or height is zero or negative). Skipping manual selection.")
        else:
            print("No region manually selected. Exiting or consider automatic detection.")
            return # 如果没有手动选择，则退出

    else: # 自动检测模式 (原代码逻辑)
        print("\n--- Running automatic bead detection ---")
        # 自动检测参数，如果手动选择模式不成功，可以再调整这些参数
        min_bead_intensity_threshold_ratio = 0.2 
        bead_min_area = 15
        bead_max_area = 1500
        padding = 15

        smoothed_image = gaussian(image_array, sigma=1)
        threshold_value = np.max(smoothed_image) * min_bead_intensity_threshold_ratio
        binary_image = smoothed_image > threshold_value
        
        selem = disk(1)
        binary_image = binary_opening(binary_image, selem)
        binary_image = binary_closing(binary_image, selem)
        
        labeled_image = label(binary_image)
        regions = regionprops(labeled_image)

        print(f"Found {len(regions)} potential regions.")
        
        for i, region in enumerate(regions):
            aspect_ratio = region.major_axis_length / region.minor_axis_length if region.minor_axis_length > 0 else 0
            if bead_min_area < region.area < bead_max_area and 1.0 <= aspect_ratio <= 3.0:
                min_row, min_col, max_row, max_col = region.bbox
                min_row_padded = max(0, min_row - padding)
                min_col_padded = max(0, min_col - padding)
                max_row_padded = min(height, max_row + padding)
                max_col_padded = min(width, max_col + padding)

                bead_segment = image_array[min_row_padded:max_row_padded, 
                                           min_col_padded:max_col_padded]
                
                if bead_segment.shape[0] > 10 and bead_segment.shape[1] > 10: 
                    selected_regions_for_processing.append({
                        'segment': bead_segment,
                        'bbox': region.bbox,
                        'source': 'auto'
                    })
                    print(f"Auto-detected bead {i+1} (area: {region.area} pixels, aspect_ratio: {aspect_ratio:.2f}) added for processing.")
                else:
                    print(f"Auto-detected bead {i+1} (area: {region.area}) due to small segment size: {bead_segment.shape}. Skipping.")
            else:
                print(f"Auto-detected bead {i+1} (area: {region.area}, aspect_ratio: {aspect_ratio:.2f}) - did not meet criteria. Skipping.")
        
        if not selected_regions_for_processing and plot_results and image_array is not None:
            plt.figure(figsize=(10, 5))
            plt.subplot(1, 2, 1)
            plt.imshow(image_array, cmap='gray')
            plt.title('Original Image')
            plt.axis('off')
            
            plt.subplot(1, 2, 2)
            plt.imshow(binary_image, cmap='gray')
            plt.title(f'Binary Image (Threshold: {threshold_value:.2f})')
            plt.axis('off')
            plt.show()


    # 处理选定的微珠
    selected_beads_fwhm = []
    bead_segments_for_plot = []

    for region_info in selected_regions_for_processing:
        bead_segment = region_info['segment']
        fwhm_um, plot_data = process_bead(bead_segment, pixel_resolution_um)
        if fwhm_um is not None:
            selected_beads_fwhm.append(fwhm_um)
            bead_segments_for_plot.append({
                'segment': bead_segment,
                'bbox': region_info['bbox'],
                'fwhm': fwhm_um,
                'plot_data': plot_data,
                'source': region_info['source']
            })
            print(f"Successfully processed a {region_info['source']} bead, FWHM: {fwhm_um:.3f} µm")

    if len(selected_beads_fwhm) > 0:
        average_fwhm = np.mean(selected_beads_fwhm)
        std_fwhm = np.std(selected_beads_fwhm)
        print(f"\n--- Results ---")
        print(f"Number of beads analyzed: {len(selected_beads_fwhm)}")
        print(f"Average Lateral Resolution (FWHM): {average_fwhm:.3f} µm ± {std_fwhm:.3f} µm")
    else:
        print("\nNo suitable beads found or processed for FWHM calculation.")
        return

    # --- 可视化 ---
    if plot_results and len(bead_segments_for_plot) > 0:
        plt.figure(figsize=(15, 10))

        # 原始图像和识别的微珠
        ax1 = plt.subplot(2, 2, 1)
        ax1.imshow(image_array, cmap='gray')
        ax1.set_title('Original Image with Identified Beads')
        ax1.axis('off')
        
        # 绘制识别出的微珠的边界框
        for region_info in bead_segments_for_plot:
            min_row, min_col, max_row, max_col = region_info['bbox']
            edge_color = 'red' if region_info['source'] == 'auto' else 'blue' # 区分手动和自动选择
            rect = plt.Rectangle((min_col, min_row), max_col - min_col, max_row - min_row,
                                 fill=False, edgecolor=edge_color, linewidth=1)
            ax1.add_patch(rect)

        # 示例微珠的强度剖面和高斯拟合
        # 优先展示手动选择的微珠，如果没有则展示第一个自动检测的
        display_bead_info = None
        for info in bead_segments_for_plot:
            if info['source'] == 'manual':
                display_bead_info = info
                break
        if display_bead_info is None:
            display_bead_info = bead_segments_for_plot[0]

        ax2 = plt.subplot(2, 2, 2)
        ax2.imshow(display_bead_info['segment'], cmap='gray')
        ax2.set_title(f"Processed Bead (FWHM: {display_bead_info['fwhm']:.3f} µm)")
        ax2.axis('off')

        x_profile_data, y_profile_data, x_fit_curve, y_fit_curve, x_positions, y_positions = display_bead_info['plot_data']

        ax3 = plt.subplot(2, 2, 3)
        ax3.plot(x_positions * pixel_resolution_um, x_profile_data, 'b-', label='X-axis Data')
        if x_fit_curve is not None:
            ax3.plot(x_positions * pixel_resolution_um, x_fit_curve, 'r--', label='X-axis Gaussian Fit')
        ax3.set_title('X-axis Intensity Profile and Fit')
        ax3.set_xlabel('Lateral position (µm)')
        ax3.set_ylabel('Normalized intensity (a.u.)')
        ax3.legend()

        ax4 = plt.subplot(2, 2, 4)
        ax4.plot(y_positions * pixel_resolution_um, y_profile_data, 'b-', label='Y-axis Data')
        if y_fit_curve is not None:
            ax4.plot(y_positions * pixel_resolution_um, y_fit_curve, 'g--', label='Y-axis Gaussian Fit')
        ax4.set_title('Y-axis Intensity Profile and Fit')
        ax4.set_xlabel('Lateral position (µm)')
        ax4.set_ylabel('Normalized intensity (a.u.)')
        ax4.legend()

        plt.tight_layout()
        plt.show()

# --- 使用示例 ---
if __name__ == "__main__":
    image_file = 'E:\code\\3-VS_proj\qt_proj\Lissajous_scan\imgsFOV\\frame_1750405833442.png' 
    image_fov_um = (27, 27) 

    # 启用手动选择模式
    main(image_file, fov_um=image_fov_um, manual_selection=True)

    # 如果您想切换回自动检测模式，可以将 manual_selection 设置为 False，并调整以下参数：
    # main(
    #     image_file, 
    #     fov_um=image_fov_um,
    #     manual_selection=False, # 切换到自动检测
    #     min_bead_intensity_threshold_ratio=0.2, 
    #     bead_min_area=15, 
    #     bead_max_area=1500, 
    #     plot_results=True
    # )