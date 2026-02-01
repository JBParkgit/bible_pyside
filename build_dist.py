"""배포판(dist/waterdbible.zip) 생성 스크립트.

실행:
    .venv/Scripts/python.exe build_dist.py

왜 필요한가
-----------
main.py / bible_view.py 는 bible_data, add, settings.json, book.ico,
Icon_word.svg, Icon_PPT.svg, bible_data.db 를 전부 "현재 작업 디렉터리 기준
상대 경로"로 읽는다 (PyInstaller의 sys._MEIPASS 를 쓰지 않음). exe를 더블
클릭했을 때의 작업 디렉터리는 exe가 있는 최상위 폴더이지, PyInstaller가
--add-data 로 넣어주는 dist/waterdbible/_internal/ 이 아니다.

즉 waterdbible.spec 의 datas=[...] 는 PyInstaller가 관리하는 위치
(_internal 내부)에만 파일을 넣어줄 뿐, 실행 시 실제로 참조되는 위치에는
아무것도 넣어주지 않는다. 이 스크립트는 그 간극을 메워서, "새 파일 하나를
추가했는데 배포판에서만 안 열린다" 류의 실수를 원천적으로 막기 위한
것이다.

규칙: 새로 추가하는 리소스 파일이 exe와 같은 폴더를 상대 경로로 참조한다면,
반드시 REQUIRED_TOP_LEVEL_ITEMS 에 등록할 것. 등록하지 않으면 이 스크립트가
빌드 후 검증 단계에서 실패하지 않으므로 조용히 누락될 수 있다.
"""
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
VENV_PYTHON = os.path.join(ROOT, ".venv", "Scripts", "python.exe")
DIST_APP_DIR = os.path.join(ROOT, "dist", "waterdbible")
FINAL_ZIP = os.path.join(ROOT, "dist", "waterdbible")  # shutil이 .zip을 붙임

# exe와 같은 폴더(top level)에 그대로 복사해야 하는 항목들.
# main.py / bible_view.py 가 상대경로("bible_data", "add", "book.ico", ...)로
# 읽는 모든 파일·폴더는 반드시 여기에 있어야 한다.
REQUIRED_TOP_LEVEL_ITEMS = [
    ("bible_data", "dir"),      # data_loaders.BibleDataLoader(base_data_path="bible_data")
    ("add", "dir"),             # CommentaryDataLoader/CrossrefDataLoader 기본 경로
    ("book.ico", "file"),       # main.py: self.setWindowIcon(QIcon('book.ico'))
    ("Icon_word.svg", "file"),  # bible_view.py: QIcon("Icon_word.svg")
    ("Icon_PPT.svg", "file"),   # bible_view.py: QIcon("Icon_PPT.svg")
]
# 위 목록과 별개로 "내용을 정제해서" 생성하는 항목 (아래 함수 참고)
GENERATED_ITEMS = ["settings.json", "bible_data.db"]


def check_sources():
    """빌드 시작 전에 원본 리소스가 실제로 존재하는지 확인한다."""
    missing = []
    for name, kind in REQUIRED_TOP_LEVEL_ITEMS:
        path = os.path.join(ROOT, name)
        ok = os.path.isdir(path) if kind == "dir" else os.path.isfile(path)
        if not ok:
            missing.append(name)
    if missing:
        sys.exit(f"[중단] 원본 리소스가 없습니다: {', '.join(missing)}")


def run_pyinstaller():
    print("[1/5] PyInstaller 빌드 실행...")
    subprocess.run(
        [VENV_PYTHON, "-m", "PyInstaller", "waterdbible.spec", "--noconfirm"],
        cwd=ROOT, check=True,
    )


def copy_required_items():
    print("[2/5] 필수 리소스를 exe와 같은 폴더로 복사...")
    for name, kind in REQUIRED_TOP_LEVEL_ITEMS:
        src = os.path.join(ROOT, name)
        dst = os.path.join(DIST_APP_DIR, name)
        if kind == "dir":
            if os.path.exists(dst):
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
        print(f"    - {name}")


def write_clean_settings():
    """개발 PC의 절대경로 등 개인 설정이 섞인 settings.json 대신,
    상대경로/기본값으로 정제한 배포용 settings.json을 생성한다."""
    print("[3/5] 배포용 settings.json 생성...")
    src_path = os.path.join(ROOT, "settings.json")
    with open(src_path, "r", encoding="utf-8") as f:
        settings = json.load(f)

    # 배포판 최초 실행 시 낯선 개인 데이터(절대경로 등)가 섞이지 않도록 정제
    settings["book"] = "창세기"
    settings["chapter"] = 1
    settings["verse_collection_file"] = "my_verse_collection.txt"

    dst_path = os.path.join(DIST_APP_DIR, "settings.json")
    with open(dst_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=4)


def write_fresh_database():
    """개발자의 개인 하이라이트/메모가 들어있지 않은 빈 DB를 생성한다."""
    print("[4/5] 배포용 bible_data.db(빈 DB) 생성...")
    dst_path = os.path.join(DIST_APP_DIR, "bible_data.db")
    if os.path.exists(dst_path):
        os.remove(dst_path)
    sys.path.insert(0, ROOT)
    from bible_database import BibleDatabase
    BibleDatabase(db_path=dst_path)


def verify_output():
    print("[검증] 배포 폴더에 필수 항목이 모두 있는지 확인...")
    missing = []
    for name, kind in REQUIRED_TOP_LEVEL_ITEMS:
        path = os.path.join(DIST_APP_DIR, name)
        ok = os.path.isdir(path) if kind == "dir" else os.path.isfile(path)
        if not ok:
            missing.append(name)
    for name in GENERATED_ITEMS:
        if not os.path.isfile(os.path.join(DIST_APP_DIR, name)):
            missing.append(name)
    if not os.path.isfile(os.path.join(DIST_APP_DIR, "waterdbible.exe")):
        missing.append("waterdbible.exe")
    if missing:
        sys.exit(f"[실패] 배포 폴더에서 누락된 항목: {', '.join(missing)}")


def make_zip():
    print("[5/5] dist/waterdbible.zip 생성...")
    zip_path = FINAL_ZIP + ".zip"
    if os.path.exists(zip_path):
        os.remove(zip_path)
    shutil.make_archive(FINAL_ZIP, "zip", root_dir=os.path.dirname(DIST_APP_DIR), base_dir="waterdbible")
    print(f"    -> {zip_path}")


if __name__ == "__main__":
    check_sources()
    run_pyinstaller()
    copy_required_items()
    write_clean_settings()
    write_fresh_database()
    verify_output()
    make_zip()
    print("완료.")
