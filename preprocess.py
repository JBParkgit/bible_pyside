# preprocess.py (수정 완료)
import os
import pickle
import traceback
# [수정] wateredbible_final12.py 대신 data_loaders.py에서 클래스를 가져옵니다.
from data_loaders import BibleDataLoader, CommentaryDataLoader, CrossrefDataLoader

def get_english_filename_base(btx_filepath):
    """ 'bible_data/kNKRV.btx' -> 'kNKRV' """
    return os.path.splitext(os.path.basename(btx_filepath))[0]

def run_preprocessing():
    """
    원본 텍스트 데이터(.btx, .txt)를 빠른 로딩을 위한 영문 이름의 .pkl 파일로 변환합니다.
    """
    print("="*50)
    print("데이터 전처리 작업을 시작합니다 (data_loaders.py 기준)...")
    print("="*50)

    # 1. 성경 데이터 전처리
    try:
        print("\n[1/3] 성경 데이터(.btx)를 .pkl로 변환 중...")
        bible_loader = BibleDataLoader("bible_data")
        available_translations = bible_loader.get_available_translations()

        if not available_translations:
            print(" -> 처리할 성경 번역본이 없습니다. 'bible_data' 폴더를 확인하세요.")
        else:
            for trans_name, btx_path in bible_loader.translation_file_map.items():
                # .pkl 파일은 이미 전처리된 파일이므로 건너뜁니다.
                if btx_path.endswith('.pkl'):
                    print(f"  - '{trans_name}'은(는) 이미 .pkl 파일이므로 건너뜁니다.")
                    continue
                try:
                    print(f"  - '{trans_name}' 처리 중...")
                    # 원본 .btx 파일로부터 데이터를 로드합니다.
                    data = bible_loader.load_translation_data(trans_name)
                    
                    filename_base = get_english_filename_base(btx_path)
                    output_path = os.path.join(bible_loader.base_data_path, f"{filename_base}.pkl")
                    
                    with open(output_path, "wb") as f:
                        pickle.dump(data, f)
                    print(f"    -> '{output_path}' 저장 완료.")
                except Exception as e:
                    print(f"    -> ERROR: '{trans_name}' 처리 중 오류 발생: {e}")
            print(" -> 성경 데이터 변환 완료.")

    except Exception as e:
        print(f"FATAL: 성경 데이터 전처리 중 심각한 오류 발생: {e}")
        traceback.print_exc()

    # 2. 주석 데이터 전처리
    try:
        print("\n[2/3] 주석 데이터(Hochma.txt)를 .pkl로 변환 중...")
        # 주석 로더에 책 정보를 제공하기 위해 임시 성경 로더를 생성합니다.
        temp_bible_loader_for_def = BibleDataLoader() 
        commentary_loader = CommentaryDataLoader("add")
        commentary_loader.set_book_definitions(temp_bible_loader_for_def.book_definitions)
        commentary_data = commentary_loader.load_commentary_data()
        
        if not commentary_data:
             print(" -> 처리할 주석 데이터가 없거나 파일을 찾을 수 없습니다.")
        else:
            output_path = os.path.join(commentary_loader.base_data_path, "Hochma.pkl")
            with open(output_path, "wb") as f:
                pickle.dump(commentary_data, f)
            print(f"  -> '{output_path}' 저장 완료.")
    except Exception as e:
        print(f"FATAL: 주석 데이터 전처리 중 심각한 오류 발생: {e}")
        traceback.print_exc()

    # 3. 관주 데이터 전처리
    try:
        print("\n[3/3] 관주 데이터(Cross_ref.txt)를 .pkl로 변환 중...")
        temp_bible_loader_for_def = BibleDataLoader()
        crossref_loader = CrossrefDataLoader("add")
        crossref_loader.set_book_definitions(temp_bible_loader_for_def.book_definitions)
        crossref_data = crossref_loader.load_crossref_data()
        
        if not crossref_data:
            print(" -> 처리할 관주 데이터가 없거나 파일을 찾을 수 없습니다.")
        else:
            output_path = os.path.join(crossref_loader.base_data_path, "Cross_ref.pkl")
            with open(output_path, "wb") as f:
                pickle.dump(crossref_data, f)
            print(f"  -> '{output_path}' 저장 완료.")
    except Exception as e:
        print(f"FATAL: 관주 데이터 전처리 중 심각한 오류 발생: {e}")
        traceback.print_exc()

    print("\n" + "="*50)
    print("모든 전처리 작업이 완료되었습니다.")
    print("이제 메인 애플리케이션을 실행하세요.")
    print("="*50)


if __name__ == "__main__":
    run_preprocessing()