import os
from PIL import Image

def resize_images_in_folder(folder_path, output_folder):
    # LINE Rich Menu 的圖片尺寸
    required_size = (2500, 1686)
    
    # 確保輸出資料夾存在，若不存在則建立
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    # 遍歷資料夾中的所有檔案
    for filename in os.listdir(folder_path):
        # 只處理圖片檔案，這裡假設圖片是 jpg 或 png 格式
        if filename.endswith(('.jpg', '.jpeg', '.png')):
            # 完整檔案路徑
            img_path = os.path.join(folder_path, filename)
            output_path = os.path.join(output_folder, filename)

            try:
                # 打開圖片
                img = Image.open(img_path)
                
                # 調整圖片大小
                img = img.resize(required_size, Image.LANCZOS)
                
                # 儲存調整後的圖片到輸出資料夾
                img.save(output_path)
                
                print(f"圖片 {filename} 已經調整大小並保存到 {output_path}")
            except Exception as e:
                print(f"處理圖片 {filename} 時發生錯誤: {e}")

# 定義資料夾路徑
input_folder ="finalrrich"
output_folder = "finalrrich_resized"

# 執行 resize 函數
resize_images_in_folder(input_folder, output_folder)