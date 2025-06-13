import cv2
import numpy as np
import os

# --- 1. 参数设置 (请根据你的情况修改) ---

# 输入文件夹：存放 512x512 16bit 原始图像
input_folder = "E:\\code\\3-VS_proj\\qt_proj\\Lissajous_scan\\imgs4914_90"

# 输出文件夹：存放二值化后的图像
output_folder = "E:\\code\\3-VS_proj\\qt_proj\\Lissajous_scan\\imgs4914_90_binary"

# 结果文件名：存放每个图像的面积比
output_txt_file = "E:\\code\\3-VS_proj\\qt_proj\\Lissajous_scan\\area_ratios.txt"

# --- 2. 主处理逻辑 (一般无需修改) ---

def process_images():
    """
    自动处理文件夹中的所有图像，进行二值化并计算面积比。
    """
    # 检查并创建输出文件夹
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        print(f"创建输出文件夹: {output_folder}")

    # 获取输入文件夹中所有的文件名
    try:
        filenames = os.listdir(input_folder)
    except FileNotFoundError:
        print(f"错误：输入文件夹 '{input_folder}' 不存在！请检查路径。")
        return

    # 打开（或创建）txt文件用于写入结果，使用 'w' 模式会覆盖旧文件
    with open(output_txt_file, 'w') as f:
        # 写入表头
        f.write("Filename,Area_Ratio\n")
        print(f"结果将保存到: {output_txt_file}")

        # 遍历所有文件
        for filename in filenames:
            # 仅处理常见的图像文件格式
            if filename.lower().endswith(('.tif', '.tiff', '.png', '.jpg', '.jpeg')):
                
                # 构建完整的文件路径
                input_path = os.path.join(input_folder, filename)
                output_path = os.path.join(output_folder, filename)

                # 读取图像，使用 cv2.IMREAD_UNCHANGED 来保留16bit深度
                image = cv2.imread(input_path, cv2.IMREAD_UNCHANGED)
                
                if image is None:
                    print(f"跳过文件（无法读取）: {filename}")
                    continue

                # 检查图像是否为512x512
                if image.shape != (512, 512):
                    print(f"警告: 图像 {filename} 的尺寸不是 512x512，为 {image.shape}。仍在处理...")

                # 使用 Otsu's 方法自动计算阈值并进行二值化
                # cv2.THRESH_OTSU 会自动忽略我们设置的阈值(这里是0)，并返回它计算出的最佳阈值
                # 图像会被转换为8位
                optimal_threshold, binary_image = cv2.threshold(
                    image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
                )

                # 保存二值化后的图像
                cv2.imwrite(output_path, binary_image)

                # 计算非零区域（白色像素）与总面积的比例
                total_pixels = image.size # 等同于 512 * 512
                white_pixels = cv2.countNonZero(binary_image)
                ratio = white_pixels / total_pixels

                # 将结果写入txt文件，格式为：文件名,比例值
                f.write(f"{filename},{ratio:.6f}\n")

                # 在控制台打印处理进度
                print(f"处理完成: {filename} | 最佳阈值: {optimal_threshold:.2f} | 面积占比: {ratio:.4f}")

    print("\n所有图像处理完毕！🎉")


# --- 3. 运行脚本 ---
if __name__ == "__main__":
    process_images()