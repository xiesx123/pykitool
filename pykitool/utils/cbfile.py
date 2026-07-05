import fnmatch
import hashlib
import os
import shutil
import time
from pathlib import Path
from typing import BinaryIO, List, Optional, Tuple, Union

from hutool import FileUtil, PathUtil, URLUtil
from loguru import logger

from pykitool.utils import cbjson

# ================================ 路径处理 ================================


# 统一转换路径为 POSIX 格式
def ap(path: str) -> str:
    if path:
        if URLUtil.is_http(path) or URLUtil.is_https(path):
            return path
        else:
            return Path(path).as_posix()
    return ""


# 获取文件名（完整）
def fullname(path: str) -> str:
    return FileUtil.get_name(path)


# 获取文件名称
def filename(path: str) -> str:
    return FileUtil.main_name(path)


# 获取文件后缀
def fileext(path: str) -> str:
    return FileUtil.get_suffix(path)


# 获取文件名和后缀（返回完整文件名、文件名、扩展名）
def name_and_ext(path: str) -> Tuple[str, str, str]:
    full = FileUtil.get_name(path)
    name = FileUtil.main_name(path)
    ext = "." + FileUtil.get_suffix(path)
    return full, name, ext


# ================================ 临时文件 ================================


# 获取或创建临时目录
def tempdir(root_dir: str = "tools") -> str:
    temp_dir = FileUtil.get_tmp_dir_path()
    temp_dir_root = os.path.join(temp_dir, root_dir.lower())
    mk(temp_dir_root)
    return temp_dir_root


# 获取临时音频文件路径
def temp_audio_wav(prefix: str = None, suffix: str = ".wav") -> str:
    return PathUtil.create_temp_file(prefix=prefix, suffix=suffix, dir_path=tempdir())


# 获取临时视频文件路径
def temp_video_mp4(prefix: str = None, suffix: str = ".mp4") -> str:
    return PathUtil.create_temp_file(prefix=prefix, suffix=suffix, dir_path=tempdir())


# 创建临时处理目录并拷贝源文件
def temp_process_path(path: str, rebuild: bool = False, output: Optional[str] = None) -> Tuple[str, str]:
    file_name = filename(path)
    if rebuild and output:
        clean(output)
    if output:
        mk(output)
        temp_file_path = ap(os.path.join(output, fullname(path)))
        cp(path, temp_file_path)
        return file_name, temp_file_path
    return file_name, path


# 拷贝文件到系统临时目录
def move_to_temp(path: Union[str, Path]) -> str:
    return cp(path, os.path.join(FileUtil.get_tmp_dir_path(), fullname(path)))


# ================================ 目录遍历 ================================


# 获取指定文件夹下子文件夹（可排除指定模式）
def sub_folders(path: Union[str, Path], exclude: str = "") -> List[str]:
    patterns = [p.strip() for p in exclude.replace(";", ",").split(",") if p.strip()]
    path = str(path)
    try:
        if not os.path.isdir(path):
            return []
        all_dirs = [name for name in os.listdir(path) if os.path.isdir(os.path.join(path, name))]
        filtered_dirs = [name for name in all_dirs if not any(fnmatch.fnmatch(name, pattern) for pattern in patterns)]
        return filtered_dirs
    except OSError as e:
        logger.error(f"Error listing folders in {path}: {str(e)}")
        return []


# 获取目录中指定索引前缀的文件
def directory_idx(path: Union[str, Path], idx: int = 0) -> Tuple[Optional[str], Optional[str]]:
    path = str(path)
    try:
        for fname in os.listdir(path):
            if fname.lower().startswith(f"{idx:02d}_"):
                file_path = ap(os.path.join(path, fname))
                if os.path.isfile(file_path):
                    return file_path, FileUtil.main_name(fname)
    except OSError as e:
        logger.error(f"Error accessing directory {path}: {str(e)}")
    return None, None


# 从基础目录提取相对路径
def relative_path(path: Union[str, Path], base_dir: str = "webapp") -> Path:
    path = Path(path)
    parts = list(path.parts)
    try:
        base_index = parts.index(base_dir)
        relative_parts = parts[base_index + 1 :]
        return Path(*relative_parts) if relative_parts else Path(".")
    except ValueError:
        return path


# ================================ 文件操作 ================================


# 写入文件内容
def write(path: Union[str, Path], data: str) -> Path:
    return FileUtil.write_utf8_string(path=path, content=data)


# 读取文件内容
def read(path: Union[str, Path]) -> str:
    return FileUtil.read_string(path=path)


def reads(paths: Union[str, bytes, List[str], Tuple[str, ...]]) -> Optional[str]:
    if isinstance(paths, (str, bytes)):
        paths = [paths]
    elif not isinstance(paths, (list, tuple)):
        return None

    content_list: List[str] = []
    for path in paths:
        try:
            content = FileUtil.read_string(path=path)
            content_list.append(content)
            logger.trace(f"Successfully read file: {path}")
        except FileNotFoundError:
            logger.error(f"File not found: {path}")
        except PermissionError:
            logger.error(f"Permission denied: {path}")
        except IOError as e:
            logger.error(f"IO error reading file {path}: {str(e)}")
        except Exception as e:
            logger.error(f"Error reading file {path}: {str(e)}")

    if content_list:
        return "\n\n".join(content_list)
    return None


# 验证路径是否有效且存在
def exist(path: Union[str, Path]) -> bool:
    return FileUtil.exist(str(path))


# 新建文件夹（可选清空已有内容）
def mk(path: Union[str, Path], is_clean: bool = False) -> Path:
    if is_clean:
        clean(path)
    return FileUtil.mkdirs(path)


# 拷贝文件到目标位置
def cp(src: Union[str, Path], dest: Union[str, Path]) -> Optional[str]:
    src = str(src)
    dest = str(dest)

    try:
        # 如果源是文件夹
        if os.path.isdir(src):
            # 确保目标路径存在
            mk(dest)

            # 遍历源文件夹中的所有内容
            for item in os.listdir(src):
                src_item = os.path.join(src, item)
                dest_item = os.path.join(dest, item)

                if os.path.isdir(src_item):
                    # 递归拷贝子文件夹
                    shutil.copytree(src_item, dest_item, dirs_exist_ok=True)
                else:
                    # 拷贝文件
                    shutil.copy2(src_item, dest_item)

            logger.debug(f"Folder contents from {src} copied to: {dest}")
            return dest

        # 如果源是文件
        else:
            file_name = os.path.basename(src)

            if os.path.isdir(dest):
                target_file = os.path.join(dest, file_name)
            else:
                target_file = dest

            target_dir = os.path.dirname(target_file)
            mk(target_dir)
            shutil.copy2(src, target_file)
            logger.debug(f"File {src} copied to: {target_file}")
            return target_file

    except FileNotFoundError:
        logger.error(f"Source file not found: {src}")
    except PermissionError:
        logger.error(f"Permission denied copying to: {dest}")
    except shutil.SameFileError:
        logger.error(f"Source and target are the same file: {src}")
    except OSError as e:
        logger.error(f"OS error copying file: {str(e)}")
    except Exception as e:
        logger.error(f"Error copying file: {str(e)}")
    return None


# 移动文件到目标位置
def mv(src: Union[str, Path], dest: Union[str, Path], is_override: bool = True) -> Path:
    return FileUtil.move(src=src, dest=dest, is_override=is_override)


# 安全删除文件
def rm(path: Union[str, Path]) -> None:
    # 防止删除系统根目录
    unsafe_paths = ["/", "C:\\", "C:/", os.path.expanduser("~")]
    if path in unsafe_paths:
        logger.error("Unsafe delete attempt blocked: {}", path)
        return
    # 删除
    return FileUtil.del_file(path)


# 安全删除文件夹
def clean(path: Union[str, Path]) -> bool:
    # 防止删除系统根目录
    unsafe_paths = ["/", "C:\\", "C:/", os.path.expanduser("~")]
    if path in unsafe_paths:
        logger.error("Unsafe delete attempt blocked: {}", path)
        return
    return FileUtil.clean(path)


# 覆盖文件（可选备份原文件）
def overwrite(src: Union[str, Path], dest: Union[str, Path], backup: bool = True) -> None:
    src = str(src)
    dest = str(dest)
    try:
        if not FileUtil.exist(src):
            raise FileNotFoundError(f"Source file does not exist: {src}")
        if backup and FileUtil.exist(dest):
            name_part = FileUtil.main_name(dest)
            ext = FileUtil.get_suffix(dest)
            target_dir = os.path.dirname(dest)
            timestamp = time.strftime("%Y%m%d%H%M%S")
            ext_str = f".{ext}" if ext else ""
            backup_path = os.path.join(target_dir, f"{name_part}_{timestamp}{ext_str}")
            FileUtil.move(dest, backup_path)
        FileUtil.move(src, dest)
        logger.debug(f"File overwritten: {dest}")
    except FileNotFoundError as e:
        raise FileNotFoundError(f"Overwrite failed: {str(e)}") from e
    except PermissionError as e:
        raise PermissionError(f"Permission denied: {str(e)}") from e
    except Exception as e:
        raise RuntimeError(f"Failed to overwrite {dest} with {src}: {str(e)}") from e


# 计算文件 MD5 值（优化块大小为 64KB 提升大文件性能）
def md5(file_obj: BinaryIO) -> str:
    md5_hash = hashlib.md5()
    # 使用 64KB 块大小，比 4KB 更适合大文件
    for chunk in iter(lambda: file_obj.read(65536), b""):
        md5_hash.update(chunk)
    return md5_hash.hexdigest()


# ================================ 调用示例 ================================

if __name__ == "__main__":

    data1 = {"name": "张三", "age": 21}
    data2 = {"name": "李四", "age": 22}
    clean(tempdir())
    tempdir1 = tempdir("tools/test1")
    tempdir2 = tempdir("tools/test2")
    tempdir3 = tempdir("tools/test3")
    output1 = PathUtil.create_temp_file(prefix="00_", suffix=".json", dir_path=tempdir1)
    output2 = PathUtil.create_temp_file(prefix="01_", suffix=".json", dir_path=tempdir1)
    print(output1)
    print(output2)

    # 路径转换为 POSIX 格式
    print(f"POSIX path: {ap(output1)}")

    # 获取完整文件名（含后缀）
    print(f"Full name: {fullname(output1)}")

    # 获取文件名（不含后缀）
    print(f"File name: {filename(output1)}")

    # 获取文件名后缀
    print(f"File name Ext: {fileext(output1)}")

    # 获取文件名和后缀
    full, fname, ext = name_and_ext(output1)
    print(f"Name and suffix: {full} | {fname} | {ext}")

    # ==================== 目录遍历示例 ====================

    # 获取指定文件夹下子文件夹
    print(f"Sub folders: {sub_folders(tempdir(), exclude='test2')}")

    # 获取目录中指定索引前缀的文件
    file_path, file_name = directory_idx(tempdir1, 0)
    print(f"Directory idx: {file_path} | {file_name}")

    # 获取相对路径
    print(f"Relative path: {relative_path('D:/Projects/creator/creator-box/webapp/sample/video_product1.json', 'webapp')}")

    # ==================== 临时文件示例 ====================

    # 获取临时目录
    print(f"Temp directory: {tempdir()}")

    # 获取临时视频文件路径
    output_mp4 = temp_video_mp4(prefix="t_")
    print(f"Temp video path: {output_mp4}")

    # 获取临时音频文件路径
    output_wav = temp_video_mp4(prefix="t_")
    print(f"Temp audio path: {output_wav}")

    # 创建临时处理目录
    file_name, temp_path = temp_process_path(output1, output=tempdir2)
    print(f"Temp process: {file_name} | {temp_path}")

    # 移动文件到临时目录
    print(f"Moved to temp: {move_to_temp(output1)}")

    # ==================== 文件操作示例 ====================

    # 写入文件内容
    print(f"Write result: {write(output1, cbjson.to_json_pretty(data1))}")
    print(f"Write result: {write(output2, cbjson.to_json_pretty(data2))}")

    # 读取文件内容
    print(f"File content: {read(output1)}")

    # 验证路径是否有效且存在
    print(f"Exist: {exist(output1)}")

    # 拷贝文件到目标位置
    print(f"Copy: {cp(output1, tempdir3)}")
    print(f"Copy: {cp(output2, tempdir3)}")
    print(f"Copy: {cp(output2, tempdir2)}")

    # # 覆盖文件（含备份原文件）
    # overwrite(output2, output1, backup=True)

    # 移动文件到目标位置
    print(f"Move: {mv(tempdir3, 'C:/Users/Administrator/Desktop/test3')}")

    # 删除文件
    rm(output_mp4)
    rm(output_wav)
