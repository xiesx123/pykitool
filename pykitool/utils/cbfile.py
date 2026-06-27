import fnmatch
import hashlib
import os
import platform
import re
import shutil
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional, Tuple, Union

from loguru import logger

# ================================ 路径处理 ================================


# 统一转换路径为 POSIX 格式
def ap(path: Optional[str]) -> str:
    if path:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        else:
            return Path(path).as_posix()
    return ""


# 获取文件名（完整）
def fullname(path: str) -> str:
    return os.path.basename(path)


# 获取文件名称
def filename(path: str) -> str:
    _, filename, _ = name_and_format(path)
    return filename


# 获取文件后缀
def fileformat(path: str) -> str:
    _, _, fileformat = name_and_format(path)
    return fileformat


# 获取文件名和后缀（返回完整文件名、文件名、扩展名）
def name_and_format(path: str) -> Tuple[str, str, str]:
    path = ap(path)
    fullname = os.path.basename(path)
    filename, fileformat = os.path.splitext(fullname)
    return fullname, filename, fileformat


# ================================ 文件读写 ================================


# 读取文件内容（支持单个路径或多个路径）
def read(paths: Union[str, bytes, List[str], Tuple[str, ...]]) -> Optional[str]:
    if isinstance(paths, (str, bytes)):
        paths = [paths]
    elif not isinstance(paths, (list, tuple)):
        return None

    content_list: List[str] = []
    for path in paths:
        try:
            with open(path, "r", encoding="utf-8") as file:
                content = file.read()
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


# 写入文件内容
def write(path: Union[str, Path], data: str) -> Optional[str]:
    try:
        path_str = str(path)
        with open(path_str, "w", encoding="utf-8") as file:
            file.write(data)
        return path_str
    except FileNotFoundError:
        logger.error(f"File not found: {path}")
    except PermissionError:
        logger.error(f"Permission denied: {path}")
    except IOError as e:
        logger.error(f"IO error writing to file {path}: {str(e)}")
    except Exception as e:
        logger.error(f"Error writing to file {path}: {str(e)}")
    return None


# ================================ 文件操作 ================================


# 拷贝文件到目标位置
def cp(source_file: Union[str, Path], target: Union[str, Path]) -> Optional[str]:
    source_file = str(source_file)
    target = str(target)
    file_name = os.path.basename(source_file)

    if os.path.isdir(target):
        target_file = os.path.join(target, file_name)
    else:
        target_file = target

    target_dir = os.path.dirname(target_file)

    try:
        mk_folder(target_dir)
        shutil.copy2(source_file, target_file)
        logger.debug(f"File {source_file} copied to: {target_file}")
        return target_file
    except FileNotFoundError:
        logger.error(f"Source file not found: {source_file}")
    except PermissionError:
        logger.error(f"Permission denied copying to: {target_file}")
    except shutil.SameFileError:
        logger.error(f"Source and target are the same file: {source_file}")
    except OSError as e:
        logger.error(f"OS error copying file: {str(e)}")
    except Exception as e:
        logger.error(f"Error copying file: {str(e)}")
    return None


# 移动文件到目标位置
def mv(source_file: Union[str, Path], target: Union[str, Path]) -> Optional[str]:
    source_file = str(source_file)
    target = str(target)
    file_name = os.path.basename(source_file)

    if os.path.isdir(target):
        target_file = os.path.join(target, file_name)
    else:
        target_file = target

    target_dir = os.path.dirname(target_file)

    try:
        mk_folder(target_dir)
        shutil.move(source_file, target_file)
        logger.debug(f"File {source_file} moved to: {target_file}")
        return target_file
    except FileNotFoundError:
        logger.error(f"Source file not found: {source_file}")
    except PermissionError:
        logger.error(f"Permission denied moving to: {target_file}")
    except shutil.SameFileError:
        logger.error(f"Source and target are the same file: {source_file}")
    except OSError as e:
        logger.error(f"OS error moving file: {str(e)}")
    except Exception as e:
        logger.error(f"Error moving file: {str(e)}")
    return None


# 拷贝文件夹到目标位置
def cp_folder(source_folder: Union[str, Path], target_folder: Union[str, Path]) -> None:
    try:
        shutil.copytree(str(source_folder), str(target_folder), dirs_exist_ok=True)
        logger.debug(f"Folder {source_folder} copied to: {target_folder}")
    except shutil.Error as e:
        logger.error(f"Error copying folder: {str(e)}")
        raise


# 新建文件夹（可选清空已有内容）
def mk_folder(path: Union[str, Path], is_clean: bool = False, exist_ok: bool = True) -> str:
    output_path = Path(path)
    if is_clean:
        rm_folder(str(path))
    output_path.mkdir(parents=True, exist_ok=exist_ok)
    return str(output_path)


# 安全删除文件
def rm(path: Optional[str]) -> None:
    try:
        if not path:
            logger.error("Invalid path: None or empty string")
            return

        # 防止删除系统根目录
        unsafe_paths = ["/", "C:\\", "C:/", os.path.expanduser("~")]
        if path in unsafe_paths:
            logger.error("Unsafe delete attempt blocked: {}", path)
            return

        if os.path.exists(path):
            os.remove(path)
            logger.trace("Successfully deleted file: {}", path)
        else:
            logger.warning("File does not exist: {}", path)
    except PermissionError:
        logger.error(f"Permission denied deleting file: {path}")
    except OSError as e:
        logger.error(f"OS error deleting file {path}: {str(e)}")
    except Exception as e:
        logger.error(f"Error deleting file {path}: {str(e)}")


# 安全删除文件夹
def rm_folder(path: Optional[str]) -> None:
    folder_path: Optional[str] = None
    try:
        if not path:
            logger.error("Invalid path: None or empty string")
            return

        path = os.path.abspath(path)

        if os.path.isfile(path):
            folder_path = os.path.dirname(path)
        elif os.path.isdir(path):
            folder_path = path
        else:
            logger.warning("Path does not exist: {}", path)
            return

        # 防止删除系统根目录
        unsafe_paths = ["/", "C:\\", "C:/", os.path.expanduser("~")]
        if folder_path in unsafe_paths:
            logger.error("Unsafe delete attempt blocked: {}", folder_path)
            return

        if os.path.exists(folder_path):
            shutil.rmtree(folder_path)
            logger.debug("Successfully deleted folder: {}", folder_path)
        else:
            logger.warning("Folder does not exist: {}", folder_path)
    except PermissionError:
        logger.error(f"Permission denied deleting folder: {folder_path}")
    except OSError as e:
        logger.error(f"OS error deleting folder {folder_path}: {str(e)}")
    except Exception as e:
        logger.error(f"Error deleting folder {folder_path}: {str(e)}")


# 覆盖文件（可选备份原文件）
def overwrite(source: Union[str, Path], target: Union[str, Path], backup: bool = True) -> None:
    source = str(source)
    target = str(target)
    try:
        if not os.path.exists(source):
            raise FileNotFoundError(f"Source file does not exist: {source}")
        if backup and os.path.exists(target):
            name_part, ext = os.path.splitext(target)
            timestamp = time.strftime("%Y%m%d%H%M%S")
            shutil.move(target, f"{name_part}_{timestamp}{ext}")
        shutil.move(source, target)
        logger.debug(f"File overwritten: {target}")
    except FileNotFoundError as e:
        raise FileNotFoundError(f"Overwrite failed: {str(e)}") from e
    except PermissionError as e:
        raise PermissionError(f"Permission denied: {str(e)}") from e
    except Exception as e:
        raise RuntimeError(f"Failed to overwrite {target} with {source}: {str(e)}") from e


# ================================ 文件信息 ================================


# 计算文件 MD5 值（优化块大小为 64KB 提升大文件性能）
def md5(file_obj: BinaryIO) -> str:
    md5_hash = hashlib.md5()
    # 使用 64KB 块大小，比 4KB 更适合大文件
    for chunk in iter(lambda: file_obj.read(65536), b""):
        md5_hash.update(chunk)
    return md5_hash.hexdigest()


# 根据文件路径计算 MD5 值
def md5_file(path: Union[str, Path]) -> str:
    with open(str(path), "rb") as f:
        return md5(f)


# 获取文件大小（单位：MB）
def get_file_size_MB(file_path: Union[str, Path]) -> float:
    return os.path.getsize(str(file_path)) / (1024 * 1024)


# 验证路径是否有效且存在
def is_valid_path(p: Any) -> bool:
    return isinstance(p, (str, Path)) and str(p).strip() != "" and Path(p).exists()


# 验证文件夹是否包含有效图片
def is_valid_image_folder(path: Union[str, Path], extensions: Tuple[str, ...] = (".png", ".jpg", ".jpeg")) -> bool:
    p = Path(path)
    if not p.exists() or not p.is_dir():
        return False
    images = list(p.glob("*"))
    return any(img.suffix.lower() in extensions for img in images)


# 清理文件名中的非法字符
def clean_filename(text: Optional[str]) -> str:
    if not text:
        return "untitled"
    text = re.sub(r'[\\/:*?"<>|]', "_", text.strip())
    text = text.strip(".")
    if not text:
        return "untitled"
    return text


# ================================ 符号链接 ================================


# 创建符号链接
def symlink(src: Union[str, Path], dest: Union[str, Path]) -> None:
    src = os.path.abspath(str(src))
    dest = os.path.abspath(str(dest))
    system = platform.system()

    try:
        if os.path.islink(dest):
            current_target = os.readlink(dest)
            if os.path.abspath(current_target) != src:
                os.unlink(dest)
                _create_symlink(src, dest, system)
                logger.info(f"[Symlink overwritten] {dest} -> {src}")
            else:
                logger.info(f"[Symlink ok] {dest} -> {src}")
        else:
            if os.path.exists(dest):
                if os.path.isdir(dest):
                    shutil.rmtree(dest)
                else:
                    rm(dest)
            _create_symlink(src, dest, system)
            logger.info(f"[Symlink created] {dest} -> {src}")
    except OSError as e:
        logger.error(f"OS error creating symlink: {str(e)}")
    except Exception as e:
        logger.error(f"Error creating symlink: {str(e)}")


# 创建符号链接辅助函数（根据操作系统选择方式）
def _create_symlink(src: str, dest: str, system: str) -> None:
    if system != "Windows":
        os.symlink(src, dest)
    else:
        subprocess.check_call(["cmd", "/c", "mklink", "/J", dest, src], shell=True)


# ================================ 目录遍历 ================================


# 获取指定文件夹下所有文件（返回字典 {文件名: 路径}）
def sub_files(path: Union[str, Path]) -> Dict[str, str]:
    result: Dict[str, str] = {}
    path = str(path)
    try:
        for entry in os.listdir(path):
            full_path = os.path.join(path, entry)
            if os.path.isfile(full_path):
                key = os.path.splitext(entry)[0]
                result[key] = full_path
    except OSError as e:
        logger.error(f"Error listing files in {path}: {str(e)}")
    return result


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
        for filename in os.listdir(path):
            if filename.lower().startswith(f"{idx:02d}_"):
                file_path = ap(os.path.join(path, filename))
                if os.path.isfile(file_path):
                    return file_path, os.path.splitext(filename)[0]
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


# ================================ 临时文件 ================================


# 获取或创建临时目录
def tempdir(root_dir: str = "tools") -> str:
    temp_dir = tempfile.gettempdir()
    temp_dir_root = os.path.join(temp_dir, root_dir.lower())
    mk_folder(temp_dir_root)
    return temp_dir_root


# 获取唯一临时文件夹路径
def temp_folder() -> str:
    return ap(os.path.join(tempdir(), next(tempfile._get_candidate_names())))


# 获取临时视频文件路径
def temp_video_mp4(prefix: str = "", suffix: str = "", ext: str = "mp4") -> str:
    prefix = prefix or next(tempfile._get_candidate_names())
    suffix_str = f"_{suffix}" if suffix else ""
    return ap(os.path.join(tempdir(), f"{prefix}{suffix_str}.{ext}"))


# 获取临时音频文件路径
def temp_audio_wav(prefix: str = "", suffix: str = "", ext: str = "wav") -> str:
    prefix = prefix or next(tempfile._get_candidate_names())
    suffix_str = f"_{suffix}" if suffix else ""
    return ap(os.path.join(tempdir(), f"{prefix}{suffix_str}.{ext}"))


# 创建临时处理目录并拷贝源文件
def temp_process_path(path: str, rebuild: bool = False, output: Optional[str] = None) -> Tuple[str, str]:
    file_name = filename(path)
    if rebuild and output:
        rm_folder(output)
    if output:
        mk_folder(output)
        temp_file_path = ap(os.path.join(output, os.path.basename(path)))
        cp(path, temp_file_path)
        logger.info("{} -> save as: {}", path, output)
        return file_name, temp_file_path
    return file_name, path


# 拷贝文件到系统临时目录
def move_to_temp(path: Union[str, Path]) -> str:
    path = str(path)
    filename = os.path.basename(path)
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, filename)
    shutil.copy(path, temp_path)
    return temp_path


# ================================ 压缩解压 ================================


# 压缩文件/文件夹到 zip 归档
def zip_files(paths: List[Union[str, Path]], output: Union[str, Path]) -> None:
    output = str(output)
    try:
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zipf:
            for path in paths:
                path = str(path)
                if os.path.isfile(path):
                    zipf.write(path, arcname=os.path.basename(path))
                elif os.path.isdir(path):
                    for root, _, files in os.walk(path):
                        for file in files:
                            full_path = os.path.join(root, file)
                            rel_path = os.path.relpath(full_path, start=os.path.dirname(path))
                            zipf.write(full_path, arcname=rel_path)
        logger.debug(f"Files compressed to: {output}")
    except zipfile.BadZipFile as e:
        logger.error(f"Bad zip file error: {str(e)}")
        raise
    except OSError as e:
        logger.error(f"OS error creating zip: {str(e)}")
        raise


# 解压 zip 归档到目录
def unzip(path: Union[str, Path], extract_dir: Union[str, Path], password: Optional[str] = None) -> None:
    path = str(path)
    extract_dir = str(extract_dir)

    if not zipfile.is_zipfile(path):
        raise ValueError(f"Invalid zip file: {path}")

    mk_folder(extract_dir)
    try:
        with zipfile.ZipFile(path, "r") as zip_ref:
            if password:
                zip_ref.setpassword(password.encode("utf-8"))
            zip_ref.extractall(extract_dir)
        logger.debug(f"Files extracted to: {extract_dir}")
    except zipfile.BadZipFile as e:
        logger.error(f"Bad zip file: {str(e)}")
        raise
    except RuntimeError as e:
        logger.error(f"Runtime error extracting zip (wrong password?): {str(e)}")
        raise


# ================================ 调用示例 ================================


if __name__ == "__main__":
    # 测试路径（请根据实际情况修改）
    test_file = "D:/Projects/test/file.txt"
    test_folder = "D:/Projects/test"

    # ==================== 路径处理示例 ====================

    # 路径转换为 POSIX 格式
    # result = ap("D:\\Projects\\test\\file.txt")
    # logger.info("POSIX path: {}", result)

    # 获取文件名（不含后缀）
    # result = filename("D:/Projects/test/video.mp4")
    # logger.info("File name: {}", result)

    # 获取完整文件名（含后缀）
    # result = fullname("D:/Projects/test/video.mp4")
    # logger.info("Full name: {}", result)

    # 获取文件名和后缀
    # full, filename, ext = name_and_suffix("D:/Projects/test/video.mp4")
    # logger.info("Name and suffix: {} | {} | {}", full, filename, ext)

    # ==================== 文件读写示例 ====================

    # 读取文件内容
    # content = read(test_file)
    # logger.info("File content: {}", content)

    # 写入文件内容
    # result = write("D:/Projects/test/output.txt", "Hello World")
    # logger.info("Write result: {}", result)

    # ==================== 文件操作示例 ====================

    # 拷贝文件
    # result = cp("D:/Projects/test/source.txt", "D:/Projects/test/backup/")
    # logger.info("Copy result: {}", result)

    # 移动文件
    # result = mv("D:/Projects/test/source.txt", "D:/Projects/test/archive/")
    # logger.info("Move result: {}", result)

    # 拷贝文件夹
    # cp_folder("D:/Projects/test/src", "D:/Projects/test/backup")
    # logger.info("Folder copied")

    # 新建文件夹
    # result = mk_folder("D:/Projects/test/new_folder", is_clean=True)
    # logger.info("Folder created: {}", result)

    # 删除文件
    # rm("D:/Projects/test/temp.txt")
    # logger.info("File deleted")

    # 删除文件夹
    # rm_folder("D:/Projects/test/temp_folder")
    # logger.info("Folder deleted")

    # 覆盖文件
    # overwrite("D:/Projects/test/new.txt", "D:/Projects/test/old.txt", backup=True)
    # logger.info("File overwritten")

    # ==================== 文件信息示例 ====================

    # 计算文件 MD5 值
    # result = md5_file(test_file)
    # logger.info("MD5: {}", result)

    # 获取文件大小（MB）
    # result = get_file_size_MB(test_file)
    # logger.info("File size: {} MB", result)

    # 验证路径是否有效
    # result = is_valid_path(test_folder)
    # logger.info("Is valid path: {}", result)

    # 验证图片文件夹是否有效
    # result = is_valid_image_folder("D:/Projects/images")
    # logger.info("Is valid image folder: {}", result)

    # 清理非法文件名字符
    # result = clean_filename("test:file*name?.txt")
    # logger.info("Cleaned filename: {}", result)

    # ==================== 符号链接示例 ====================

    # 创建符号链接
    # symlink("D:/Projects/source", "D:/Projects/link")
    # logger.info("Symlink created")

    # ==================== 目录遍历示例 ====================

    # 获取指定文件夹下所有文件
    # result = sub_files(test_folder)
    # logger.info("Sub files: {}", result)

    # 获取指定文件夹下子文件夹
    # result = sub_folders(test_folder, exclude="__pycache__,*.egg-info")
    # logger.info("Sub folders: {}", result)

    # 获取目录中指定索引前缀的文件
    # file_path, file_name = directory_idx("D:/Projects/test/tts", 0)
    # logger.info("Directory idx: {} | {}", file_path, file_name)

    # 获取相对路径
    # result = relative_path("D:/Projects/webapp/static/js/app.js", "webapp")
    # logger.info("Relative path: {}", result)

    # ==================== 临时文件示例 ====================

    # 获取临时目录
    # result = tempdir()
    # logger.info("Temp directory: {}", result)

    # 获取临时文件夹路径
    # result = temp_folder()
    # logger.info("Temp folder: {}", result)

    # 获取临时视频文件路径
    # result = temp_video_mp4(prefix="test", suffix="clip")
    # logger.info("Temp video path: {}", result)

    # 获取临时音频文件路径
    # result = temp_audio_wav(prefix="test", suffix="segment")
    # logger.info("Temp audio path: {}", result)

    # 创建临时处理目录
    # file_name, temp_path = temp_process_path("D:/video.mp4", output="D:/temp/process")
    # logger.info("Temp process: {} | {}", file_name, temp_path)

    # 移动文件到临时目录
    # result = move_to_temp(test_file)
    # logger.info("Moved to temp: {}", result)

    # ==================== 压缩解压示例 ====================

    # 压缩文件
    # zip_files(["D:/Projects/test/file1.txt", "D:/Projects/test/folder"], "D:/output.zip")
    # logger.info("Files zipped")

    # 解压文件
    # unzip("D:/output.zip", "D:/extracted")
    # logger.info("Files unzipped")

    # ==================== 下载示例 ====================

    # 使用 yt-dlp 下载视频
    # result = ytdlp_download(url="https://www.youtube.com/watch?v=xxxxx")
    # logger.info("Downloaded video: {}", result)

    # HTTP 下载文件
    # result = http_download("https://example.com/file.zip", save_folder="D:/downloads")
    # logger.info("Downloaded file: {}", result)

    # ==================== SRT 字幕示例 ====================

    # 加载 SRT 字幕文件
    # segments = load_srt("D:/Projects/test/subtitle.srt")
    # logger.info("Loaded segments: {}", len(segments))

    # 写入 SRT 字幕文件
    # data = [{"start": 0.0, "end": 2.5, "text": "Hello"}, {"start": 2.5, "end": 5.0, "text": "World"}]
    # result = write_srt(data, "D:/Projects/test/output.srt")
    # logger.info("SRT written: {}", result)

    # 移除空白和重复字幕
    # result = remove_blank_and_duplicate_srt("D:/Projects/test/subtitle.srt")
    # logger.info("SRT cleaned: {}", result)

    # 从 JSON 生成 SRT 字幕
    # result = generate_srt("D:/Projects/test/data.json", "text", "D:/Projects/test/output.srt")
    # logger.info("SRT generated: {}", result)
