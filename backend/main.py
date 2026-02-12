from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import FileResponse
import subprocess
import asyncio
import json
import os
import platform
import shutil
import re
from pathlib import Path
from datetime import datetime
from enum import Enum

class Platform(Enum):
    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "darwin"

class PlatformConfig:
    """平台配置管理器"""
    _instance = None
    _platform = None
    _shell_command = None
    _encoding = None
    _opencode_command = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """初始化平台配置"""
        self._platform = platform.system().lower()

        if self._platform == "windows":
            self._shell_command = "cmd.exe /c"
            self._encoding = "gbk"
        else:  # Linux or MacOS
            self._shell_command = "/bin/bash -c"
            self._encoding = "utf-8"

    @property
    def platform(self) -> str:
        return self._platform

    @property
    def shell_command(self) -> str:
        return self._shell_command

    @property
    def encoding(self) -> str:
        return self._encoding

    @property
    def opencode_command(self) -> str:
        """获取opencode命令（支持不同系统）"""
        if self._opencode_command:
            return self._opencode_command

        # 首先尝试 which/where 命令查找
        try:
            if self._platform == "windows":
                result = subprocess.run(
                    "where opencode",
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
            else:
                result = subprocess.run(
                    "which opencode",
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=5
                )

            if result.returncode == 0 and result.stdout.strip():
                self._opencode_command = "opencode"
                return self._opencode_command
        except Exception:
            pass

        # 默认使用 opencode
        self._opencode_command = "opencode"
        return self._opencode_command

    def is_windows(self) -> bool:
        return self._platform == "windows"

    def is_linux(self) -> bool:
        return self._platform == "linux"

    def is_macos(self) -> bool:
        return self._platform == "darwin"

# 全局平台配置实例
platform_config = PlatformConfig()

app = FastAPI()

# 允许跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 配置文件路径
CONFIG_FILE = Path(__file__).parent / "config.json"
PROJECTS_DIR = None
CURRENT_PROJECT = {"path": None, "name": None}

def convert_windows_path_to_native(windows_path: str) -> str:
    """将Windows路径格式转换为当前系统的原生路径格式"""
    if not windows_path:
        return windows_path

    # 使用 Path 处理，自动转换为当前系统的路径格式
    path = Path(windows_path)

    # 处理相对路径
    if not path.is_absolute():
        # 对于相对路径，也需要确保格式正确
        path = Path(windows_path.replace('\\', '/'))

    return str(path)

def load_config():
    """加载配置文件（跨平台支持）"""
    global PROJECTS_DIR
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
            raw_projects_dir = config.get("projects_dir")

            # 转换为当前系统的路径格式
            if raw_projects_dir:
                PROJECTS_DIR = convert_windows_path_to_native(raw_projects_dir)
            else:
                PROJECTS_DIR = None
    else:
        PROJECTS_DIR = None

load_config()


def get_thumbnail_path(project_path: str) -> str:
    """获取项目的缩略图路径（跨平台支持）"""
    # 使用 pathlib 确保跨平台兼容性
    project_dir = Path(project_path)
    thumbnail_path = project_dir / ".thumbnail.png"
    return str(thumbnail_path)


class ProjectRequest(BaseModel):
    name: str


def run_command_sync(command: str, cwd: str = None) -> str:
    """同步执行命令（跨平台支持）"""
    try:
        # 根据平台选择shell和编码
        shell_cmd = f'{platform_config.shell_command} "{command}"' if platform_config.is_windows() else f"{platform_config.shell_command} '{command}'"
        result = subprocess.run(
            shell_cmd,
            shell=True,
            capture_output=True,
            text=True,
            encoding=platform_config.encoding,
            errors='replace',
            cwd=cwd
        )
        return result.stdout + result.stderr
    except Exception as e:
        return f"Error: {str(e)}"


def build_opencode_command(prompt: str) -> str:
    """构建opencode命令（跨平台支持）"""
    # 获取opencode命令
    opencode_cmd = platform_config.opencode_command

    # 转义引号 - Windows和Linux/Mac处理方式相同
    escaped_prompt = prompt.replace('"', '\\"')

    # 构建完整的命令
    # 使用双引号包裹整个参数，确保跨平台兼容
    full_command = f'{opencode_cmd} run "/ui-ux-pro-max [ROLE] 你是一个专业的前端开发者，擅长将需求转化为精美的网页原型\\n[TASK] 根据用户需求生成一个完整的单文件HTML网页，如果项目中已经存在单文件HTML网页，那就先分析用户需求是否想在原有文件风格基础上进行修改，一般来说只要用户没有特意提出类似于"重新生成XXX"的需求，那就直接在原有文件风格基础上进行修改\\n[REQUIREMENTS]\\n1. 输出完整的 HTML5 代码（包含 CSS 和 JavaScript）\\n2. 将代码保存为 index.html（直接覆盖）\\n3. 无论用户需求是什么语言，生成的页面内容必须是中文为主要语言\\n4. 只生成前端代码，不需要后端逻辑\\n5. 基于用户需求自行选择UI风格，要求风格必须简洁，美观，符合现代审美\\n6. 确保 HTML 结构完整，可直接在浏览器中打开\\n[INPUT] 用户需求：{escaped_prompt}"'

    return full_command


@app.get("/api/projects")
async def get_projects():
    """获取项目列表（按创建时间降序排列）"""
    if not PROJECTS_DIR or not os.path.exists(PROJECTS_DIR):
        return {"projects": [], "current_project": CURRENT_PROJECT}
    
    items = os.listdir(PROJECTS_DIR)
    projects_with_time = []
    
    for item in items:
        project_path = os.path.join(PROJECTS_DIR, item)
        if os.path.isdir(project_path):
            # 获取目录的修改时间
            try:
                stat = os.stat(project_path)
                mtime = stat.st_mtime
            except:
                mtime = 0
            projects_with_time.append((item, mtime))
    
    # 按修改时间降序排列（最新的在前）
    projects_with_time.sort(key=lambda x: x[1], reverse=True)
    
    # 提取排序后的项目名称
    projects = [item[0] for item in projects_with_time]
    
    return {"projects": projects, "current_project": CURRENT_PROJECT}


@app.post("/api/projects")
async def create_project(request: ProjectRequest):
    """创建新项目"""
    if not PROJECTS_DIR:
        raise HTTPException(status_code=400, detail="未配置项目目录")
    
    project_path = os.path.join(PROJECTS_DIR, request.name)
    if os.path.exists(project_path):
        raise HTTPException(status_code=400, detail=f"项目 {request.name} 已存在")
    
    os.makedirs(project_path, exist_ok=True)
    return {"message": f"项目 {request.name} 创建成功", "project": request.name}


@app.post("/api/projects/{name}/select")
async def select_project(name: str):
    """选择项目"""
    if not PROJECTS_DIR:
        raise HTTPException(status_code=400, detail="未配置项目目录")
    
    project_path = os.path.join(PROJECTS_DIR, name)
    if not os.path.exists(project_path):
        raise HTTPException(status_code=404, detail=f"项目 {name} 不存在")
    
    CURRENT_PROJECT["path"] = project_path
    CURRENT_PROJECT["name"] = name
    
    # 检测是否有 index.html
    has_html = os.path.exists(os.path.join(project_path, "index.html"))
    
    return {
        "message": f"已切换到项目 {name}",
        "current_project": CURRENT_PROJECT,
        "has_html": has_html
    }


@app.delete("/api/projects/{name}")
async def delete_project(name: str):
    """删除项目"""
    if not PROJECTS_DIR:
        raise HTTPException(status_code=400, detail="未配置项目目录")
    
    project_path = os.path.join(PROJECTS_DIR, name)
    if not os.path.exists(project_path):
        raise HTTPException(status_code=404, detail=f"项目 {name} 不存在")
    
    # 如果删除的是当前项目，先退出
    if CURRENT_PROJECT["name"] == name:
        CURRENT_PROJECT["path"] = None
        CURRENT_PROJECT["name"] = None

    shutil.rmtree(project_path)
    return {"message": f"项目 {name} 已删除"}


class RenameRequest(BaseModel):
    new_name: str


@app.post("/api/projects/{name}/rename")
async def rename_project(name: str, request: RenameRequest):
    """重命名项目"""
    if not PROJECTS_DIR:
        raise HTTPException(status_code=400, detail="未配置项目目录")

    old_project_path = os.path.join(PROJECTS_DIR, name)
    if not os.path.exists(old_project_path):
        raise HTTPException(status_code=404, detail=f"项目 {name} 不存在")

    new_name = request.new_name.strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="新名称不能为空")

    if new_name == name:
        return {"message": "名称未变化", "old_name": name, "new_name": new_name}

    new_project_path = os.path.join(PROJECTS_DIR, new_name)
    if os.path.exists(new_project_path):
        raise HTTPException(status_code=400, detail=f"项目 {new_name} 已存在")

    # 重命名目录
    os.rename(old_project_path, new_project_path)

    # 如果重命名的是当前项目，更新 CURRENT_PROJECT
    if CURRENT_PROJECT["name"] == name:
        CURRENT_PROJECT["path"] = new_project_path
        CURRENT_PROJECT["name"] = new_name

    return {"message": f"项目 {name} 已重命名为 {new_name}", "old_name": name, "new_name": new_name}


@app.post("/api/projects/exit")
async def exit_project():
    """退出当前项目"""
    CURRENT_PROJECT["path"] = None
    CURRENT_PROJECT["name"] = None
    return {"message": "已退出当前项目", "current_project": CURRENT_PROJECT}


class GenerateRequest(BaseModel):
    prompt: str


@app.post("/api/generate")
async def generate_webpage(request: GenerateRequest):
    """使用 AI 生成网页（跨平台支持）"""
    if not CURRENT_PROJECT.get("path"):
        raise HTTPException(status_code=400, detail="请先选择一个项目")

    # 获取原始提示词
    original_prompt = request.prompt

    # 使用跨平台命令构建函数
    command = build_opencode_command(request.prompt)

    cwd = CURRENT_PROJECT.get("path")
    loop = asyncio.get_event_loop()
    output = await loop.run_in_executor(
        None,
        lambda: run_command_sync(command, cwd)
    )

    # 检查是否生成了 index.html
    index_path = os.path.join(cwd, "index.html")
    if os.path.exists(index_path):
        # 生成成功后记录提示词
        prompt_file = os.path.join(cwd, "prompt.txt")
        try:
            # 获取当前时间
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if os.path.exists(prompt_file):
                # 已有文件，追加新记录
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                # 最后一行可能是空行，需要过滤
                existing_lines = [line.strip() for line in lines if line.strip()]
                next_num = len(existing_lines) + 1
            else:
                # 新建文件
                next_num = 1

            # 追加新的提示词记录：序号 [时间] 原始提示词
            with open(prompt_file, 'a', encoding='utf-8') as f:
                f.write(f"{next_num} [{timestamp}] {original_prompt}\n")
        except Exception as e:
            # 记录失败不影响生成结果，只打印日志
            print(f"记录提示词失败: {e}")

        # 生成成功后由前端截图
        # 后端不再处理缩略图
        thumbnail_updated = True

        return {
            "success": True,
            "message": "网页生成成功",
            "output": output,
            "html_url": "/api/html",
            "thumbnail_updated": thumbnail_updated
        }
    else:
        return {
            "success": False,
            "message": "生成失败，未找到 index.html",
            "output": output
        }


@app.get("/api/html")
async def get_html():
    """获取当前项目的 index.html"""
    if not CURRENT_PROJECT.get("path"):
        raise HTTPException(status_code=400, detail="请先选择一个项目")
    
    index_path = os.path.join(CURRENT_PROJECT["path"], "index.html")
    if not os.path.exists(index_path):
        raise HTTPException(status_code=404, detail="index.html 不存在")
    
    return FileResponse(index_path)


@app.get("/api/prompts")
async def get_prompts():
    """获取当前项目的提示词历史记录"""
    if not CURRENT_PROJECT.get("path"):
        raise HTTPException(status_code=400, detail="请先选择一个项目")
    
    prompt_file = os.path.join(CURRENT_PROJECT["path"], "prompt.txt")
    if not os.path.exists(prompt_file):
        return {"prompts": [], "current_project": CURRENT_PROJECT}
    
    try:
        with open(prompt_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        # 过滤空行并返回
        prompts = [line.strip() for line in lines if line.strip()]
        return {"prompts": prompts, "current_project": CURRENT_PROJECT}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取提示词记录失败: {str(e)}")


@app.get("/api/projects/list")
async def get_all_projects(page: int = 1, page_size: int = 6):
    """获取所有项目列表（用于项目卡片展示）- 支持分页"""
    if not CURRENT_PROJECT.get("path"):
        raise HTTPException(status_code=400, detail="请先选择一个项目")
    
    current_project_path = os.path.abspath(CURRENT_PROJECT["path"])
    current_project_name = os.path.basename(current_project_path)  # 当前项目名称
    projects_root = os.path.abspath("..")
    projects_dir = os.path.join(projects_root, "projects")
    
    if not os.path.exists(projects_dir):
        return {
            "projects": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
            "total_pages": 0,
            "current_project": CURRENT_PROJECT
        }
    
    all_projects = []
    # 遍历所有子目录
    for item in os.listdir(projects_dir):
        item_path = os.path.join(projects_dir, item)
        if os.path.isdir(item_path) and item != current_project_name:  # 排除当前项目
            # 获取项目信息
            project_name = item
            created_time = None
            
            # 尝试获取创建时间或修改时间
            try:
                stat = os.stat(item_path)
                # 使用修改时间作为项目"创建时间"
                mod_time = stat.st_mtime
                created_time = datetime.fromtimestamp(mod_time).strftime("%Y-%m-%d")
            except:
                created_time = "未知"
            
            # 检查是否有 index.html
            has_html = os.path.exists(os.path.join(item_path, "index.html"))
            
            # 获取第一条提示词
            first_prompt = None
            first_prompt_time = None
            prompt_file = os.path.join(item_path, "prompt.txt")
            if os.path.exists(prompt_file):
                try:
                    with open(prompt_file, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                    # 过滤空行
                    valid_lines = [l.strip() for l in lines if l.strip()]
                    if valid_lines:
                        # 解析第一条：格式 "序号 [时间] 内容"
                        first_line = valid_lines[0]
                        # 提取时间
                        time_match = re.search(r'\[([^\]]+)\]', first_line)
                        if time_match:
                            first_prompt_time = time_match.group(1)
                        # 提取内容（去掉序号和时间）
                        content = re.sub(r'^\d+\s*\[\s*[^]]*\s*\]\s*', '', first_line).strip()
                        first_prompt = content if content else "暂无描述"
                except:
                    pass
            
            all_projects.append({
                "name": project_name,
                "created_time": created_time,
                "has_html": has_html,
                "first_prompt": first_prompt,
                "first_prompt_time": first_prompt_time
            })
    
    # 按创建时间降序排列（最新的在前）- 用户说可能需要按时间排序
    all_projects.sort(key=lambda x: x.get("created_time", ""), reverse=True)
    
    # 分页计算
    total = len(all_projects)
    total_pages = (total + page_size - 1) // page_size
    
    # 获取当前页数据
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_projects = all_projects[start_idx:end_idx]
    
    return {
        "projects": page_projects,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "current_project": CURRENT_PROJECT
    }


@app.get("/api/projects/{name}/thumbnail")
async def get_thumbnail(name: str):
    """获取项目的缩略图"""
    if not PROJECTS_DIR:
        raise HTTPException(status_code=400, detail="未配置项目目录")

    project_path = os.path.join(PROJECTS_DIR, name)
    thumbnail_path = get_thumbnail_path(project_path)

    if not os.path.exists(thumbnail_path):
        # 如果缩略图不存在，返回默认占位图或404
        raise HTTPException(status_code=404, detail="缩略图不存在")

    return FileResponse(thumbnail_path, media_type="image/png")


@app.post("/api/projects/thumbnail")
async def upload_thumbnail(request: Request):
    """
    保存前端传来的缩略图
    需要在请求中携带当前项目信息
    """
    if not CURRENT_PROJECT.get("path"):
        raise HTTPException(status_code=400, detail="请先选择一个项目")

    try:
        # 解析 multipart form data
        form = await request.form()
        thumbnail_file = form.get("thumbnail")

        if not thumbnail_file:
            raise HTTPException(status_code=400, detail="没有上传文件")

        # 获取项目路径并保存
        project_path = CURRENT_PROJECT["path"]
        thumbnail_path = get_thumbnail_path(project_path)

        # 保存文件
        with open(thumbnail_path, "wb") as f:
            content = await thumbnail_file.read()
            f.write(content)

        print(f"[缩略图] 已保存: {thumbnail_path}")
        return {"success": True, "message": "缩略图已保存"}

    except Exception as e:
        print(f"[缩略图] 保存失败: {e}")
        raise HTTPException(status_code=500, detail=f"保存失败: {e}")


@app.get("/")
async def serve_frontend():
    """提供前端静态文件"""
    frontend_path = Path(__file__).parent.parent / "frontend" / "dist"
    index_file = frontend_path / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "请先构建前端: cd frontend && npm run build"}
