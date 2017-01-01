"""生成指定年份的随机间隔提交（空提交，回填作者/提交时间）。

用法:
    python3 backend/scripts/gen_random_commits.py <年份> [最小间隔(小时)] [最大间隔(小时)]

示例:
    python3 backend/scripts/gen_random_commits.py 2017 3 12
"""
import os
import random
import subprocess
import sys
from datetime import datetime, timedelta

# 仓库根目录：脚本位于 <repo>/backend/scripts/ 下，向上两级即仓库根
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 与现有历史风格一致的中文 conventional commit 信息
MESSAGES = [
    "feat: 功能细节完善",
    "chore: 更新依赖配置",
    "docs: 补充使用说明",
    "docs: 更新项目文档",
    "refactor: 优化代码结构",
    "style: 调整页面样式",
    "fix: 修复已知小问题",
    "chore: 日常维护与巡检",
]


def random_time(base_date: datetime) -> str:
    """在 base_date 当天 8:00-23:59 之间随机一个时间。"""
    h = random.randint(8, 23)
    m = random.randint(0, 59)
    s = random.randint(0, 59)
    dt = base_date.replace(hour=h, minute=m, second=s, microsecond=0)
    return dt.strftime("%Y-%m-%dT%H:%M:%S+08:00")


def git_commit(date_str: str, message: str) -> bool:
    """创建一个空提交，并回填作者与提交时间。"""
    env = os.environ.copy()
    env["GIT_AUTHOR_DATE"] = date_str
    env["GIT_COMMITTER_DATE"] = date_str

    r = subprocess.run(
        ["git", "commit", "--allow-empty", "-m", message],
        cwd=REPO, env=env, capture_output=True, text=True,
    )
    if r.returncode != 0:
        print(f"commit failed: {r.stderr.strip()}")
    return r.returncode == 0


def main():
    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2017
    min_gap = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    max_gap = int(sys.argv[3]) if len(sys.argv) > 3 else 12

    start = datetime(year, 1, 1)
    end = datetime(year, 12, 31, 23, 59, 59)

    current = start
    count = 0

    while current <= end:
        date_str = random_time(current)
        message = random.choice(MESSAGES)
        if git_commit(date_str, message):
            count += 1
        gap = random.randint(min_gap, max_gap)
        current += timedelta(hours=gap)

    print(f"Year {year}: {count} commits created (random intervals {min_gap}-{max_gap} hours)")


if __name__ == "__main__":
    main()
