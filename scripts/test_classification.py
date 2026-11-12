import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from classification import classify, extract_eligibility, classification_fields
from migrate_notices import migrate
from notice_schema import ensure_notice_schema


class ClassificationTests(unittest.TestCase):
    def test_role_and_purpose_take_precedence(self):
        cases = [
            ('SW중심대학사업단 가치확산서포터즈(근로학생) 모집', '', '근로·알바·학생조교'),
            ('성균관대학교 창업지원단 직원 채용', '', '취업·인턴·현장실습'),
            ('부트캠프 사업단 행정조교 모집', '학사 학위 이상, 전일제, 월 2,156,900원, 4대 보험', '취업·인턴·현장실습'),
            ('뇌과학 연구실 학부생 연구 인턴 모집', '', '연구경험·학술지원'),
            ('MRI 기억 실험 참여자 모집', '', '실험·설문·인터뷰 참여'),
            ('[법학연구원] 2026학년도 법학연구원 채용공고', '대학원 근로장학생을 아래와 같이 채용합니다.', '근로·알바·학생조교'),
            ('연구조교 모집', '본교 학부생, 자료수집, 시간당 11,000원', '근로·알바·학생조교'),
            ('전국 지역인재 7급 수습직원 추천자 선발', '', '취업·인턴·현장실습'),
            ('[HUSS] 2026학년도 사업단 설명회 안내', '', '행사·강연·문화'),
            ('마이크로디그리 신청 안내', '', '교육·역량개발'),
            ('2026학년도 현장실습 학생 지원 신청 안내', '', '취업·인턴·현장실습'),
            ('CAMPUS Asia 일본파견 교환장학생 모집', '', '국제교류·해외연수'),
            ('성적우수 장학생 선발', '', '장학·학비지원'),
            ('SKKU-BA-DIVE 프로그램 모집', '', '국제교류·해외연수'),
            ('학생증 발급 신청 안내', '', '학사·행정'),
            ('기숙사 생활지도조교 모집', '', '근로·알바·학생조교'),
            ('행복기숙사 입주생 모집', '', '생활·복지·시설'),
            ('WISET 취업탐색 멘토링 멘티 모집', '', '교육·역량개발'),
            ('서울런 대학생 멘토 모집', '', '봉사·멘토링·서포터즈'),
            ('글로벌 창업경진대회 참가팀 모집', '', '공모전·경진대회'),
            ('실험실창업탐색팀 모집', '', '창업·사업화'),
            ('야구부 재능 기부 프로그램 참여자 모집', '', '생활·복지·시설'),
        ]
        for title, body, expected in cases:
            with self.subTest(title=title):
                self.assertEqual(classify(title, body)['main_category'], expected)

    def test_unknown_and_missing_body_are_not_claimed_verified(self):
        self.assertIsNone(classify('내용이 불명확한 안내', '첨부 참조')['main_category'])
        self.assertEqual(classify('장학생 모집')['classification_status'], 'needs_review')

    def test_exclusions_and_boolean_conditions_preserved(self):
        source = '대학원 재학생(휴학생·수료생 불가), 전공 A 또는 B, 평점 3.5 이상 및 소득 4구간 이하'
        conditions = extract_eligibility(source)
        for key in ['education', 'enrollment', 'major', 'gpa', 'income', 'restrictions']:
            self.assertIn(source, conditions[key])
        self.assertEqual(conditions['evidence'], [source])
        self.assertEqual(extract_eligibility('공지사항 참조')['status'], 'not_stated')

    def test_condition_sections_do_not_include_schedule(self):
        conditions = extract_eligibility('공지사항 참조', '1. 지원자격\n- 본교 재학생\n- 휴학생 불가\n2. 접수기간\n2026년 11월 1일')
        self.assertIn('휴학생 불가', conditions['restrictions'])
        self.assertNotIn('2026년 11월 1일', conditions['evidence'])

    def test_invalid_llm_category_falls_back(self):
        fields = classification_fields('근로학생 모집', '시급 업무', '재학생', '시급', '교내장학',
                                       {'main_category': '장학·학비지원', 'subcategory': '국가근로'})
        self.assertEqual(fields['main_category'], '근로·알바·학생조교')

    def test_llm_conflict_or_empty_body_stays_reviewable(self):
        result = {'main_category': '장학·학비지원', 'subcategory': '장학생 선발'}
        fields = classification_fields('근로학생 모집', '시급 업무', '재학생', '시급', '교내장학', result)
        self.assertEqual(fields['classification_status'], 'needs_review')
        fields = classification_fields('장학생 모집', '', '', '', '', result)
        self.assertEqual(fields['classification_status'], 'needs_review')

    def test_migration_is_lossless_idempotent_and_constrained(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'scholar.db'
            conn = sqlite3.connect(path)
            with conn:
                ensure_notice_schema(conn)
                for table in ('jobs', 'scholarships'):
                    conn.execute(f'''INSERT INTO {table} (id,target_audience,organizer,deadline,benefit,category,title,full_text)
                        VALUES (1,'휴학생 불가','대학','미정','시급 11000원','교내장학','근로학생 모집','학생 근로 모집')''')
                conn.execute("CREATE TABLE notice_sources (notice_type TEXT, notice_id INTEGER, source_url TEXT)")
                conn.execute("INSERT INTO notice_sources VALUES ('job',1,'https://example.test/1')")
            original = conn.execute('SELECT id,target_audience,category,title,full_text FROM jobs').fetchall()
            conn.close()
            first = migrate(path)
            self.assertEqual(first['updated_rows'], 2)
            self.assertTrue(Path(first['backup']).is_file())
            self.assertEqual(migrate(path)['updated_rows'], 0)
            conn = sqlite3.connect(path)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM notices').fetchone()[0], 1)
            self.assertEqual(conn.execute('SELECT id,target_audience,category,title,full_text FROM jobs').fetchall(), original)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM notice_sources').fetchone()[0], 1)
            self.assertEqual(json.loads(conn.execute('SELECT eligibility_conditions FROM jobs').fetchone()[0])['enrollment'], ['휴학생 불가'])
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("UPDATE jobs SET main_category='장학·학비지원',subcategory='국가근로'")
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("UPDATE jobs SET eligibility_conditions='invalid'")
            conn.execute("UPDATE jobs SET classification_status='reviewed',classification_reason='직접 검토'")
            conn.commit()
            migrate(path)
            self.assertEqual(conn.execute('SELECT classification_reason FROM jobs').fetchone()[0], '직접 검토')
            conn.close()


if __name__ == '__main__':
    unittest.main()
