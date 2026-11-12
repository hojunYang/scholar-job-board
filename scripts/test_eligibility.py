import unittest
from eligibility import extract_profile


class EligibilityTests(unittest.TestCase):
    def profile(self, text):
        return extract_profile('공지', '', text)

    def test_grade_range_and_lower_bound(self):
        self.assertEqual(self.profile('학부 2~4학년 재학생')['student_years'], [2, 3, 4])
        self.assertEqual(self.profile('2학년 이상 재학생')['student_years'], [2, 3, 4, 5, 6])
        self.assertEqual(self.profile('학사과정 1~4학년 재학생')['student_years'], [1, 2, 3, 4])

    def test_calendar_year_is_not_student_year(self):
        self.assertEqual(self.profile('2026학년도 2학년 재학생')['student_years'], [2])
        result=extract_profile('장학', '지원자격\n2학년 재학생\n제출서류\n성적증명서(1학년 1학기)')
        self.assertEqual(result['student_years'], [2])

    def test_past_year_grades_are_not_eligible_years(self):
        result = self.profile('2학년 재학생으로 대학 1학년 전체 평균 성적 85점 이상')
        self.assertEqual(result['student_years'], [2])

    def test_parenthesized_exclusion_does_not_deny_enrollment(self):
        result = self.profile('학부 재학생(휴학생 및 수료생 불가)')
        self.assertIn('enrolled', result['enrollment_statuses'])
        self.assertNotIn('on_leave', result['enrollment_statuses'])
        self.assertNotIn('completed', result['enrollment_statuses'])
        self.assertEqual(result['field_states']['studentYear'], 'any')

    def test_multiple_statuses_and_exclusions(self):
        result = self.profile('학사과정 재학생 또는 휴학생, 수료생 지원 가능, 졸업생은 지원 불가')
        self.assertIn('enrolled', result['enrollment_statuses'])
        self.assertIn('on_leave', result['enrollment_statuses'])
        self.assertIn('completed', result['enrollment_statuses'])
        self.assertNotIn('graduated', result['enrollment_statuses'])

    def test_income_is_numeric_and_ors_are_not_flattened(self):
        result = self.profile('학자금 지원구간 4구간 이하')
        self.assertEqual(result['income_tiers'], ['0', '1', '2', '3', '4'])
        self.assertEqual(result['field_states']['incomeTier'], 'known')
        self.assertEqual(self.profile('학자금 지원 구간 8구간(국가장학금 소득 8분위) 이내인 자')['income_tiers'], [str(n) for n in range(9)])
        self.assertEqual(self.profile('소득 8분위 이하 또는 다자녀 가구')['field_states']['incomeTier'], 'ambiguous')
        self.assertEqual(self.profile('기준 중위소득 100% 이하')['field_states']['incomeTier'], 'ambiguous')

    def test_degree_is_not_student_level(self):
        result = self.profile('학사 학위 이상 소지자(전문학사 및 졸업예정자 불가)')
        self.assertEqual(result['degree_levels'], ['bachelor', 'master', 'doctorate'])
        self.assertEqual(result['field_states']['studyLevel'], 'unknown')
        self.assertEqual(result['graduation_statuses'], ['graduated'])
        self.assertEqual(result['field_states']['graduationStatus'], 'known')
        self.assertEqual(self.profile('박사학위 소지자')['degree_levels'], ['doctorate'])
        self.assertIsNone(self.profile('학사과정 재학생')['degree_levels'])

    def test_preferred_degree_does_not_raise_requirement(self):
        result = self.profile('학사학위 이상 소지자, 석사학위 소지자 우대')
        self.assertEqual(result['degree_levels'], ['bachelor', 'master', 'doctorate'])
        result = extract_profile('직원 모집', '1. 지원자격\n학사학위 이상 소지자\n2. 우대사항\n석사학위 소지자\n경력 5년 이상\n3. 제출서류\n이력서', '')
        self.assertEqual(result['degree_levels'], ['bachelor', 'master', 'doctorate'])
        self.assertIsNone(result['experience_min'])

    def test_experience_and_work_time(self):
        self.assertEqual(self.profile('관련 경력 3년 이상')['experience_min'], 3)
        self.assertEqual(self.profile('신입/경력 무관')['field_states']['experienceYears'], 'any')
        self.assertEqual(self.profile('전일제 근무 가능자')['requires_full_time'], 1)
        self.assertEqual(self.profile('전일제 근무 가능자 우대')['field_states']['workAvailability'], 'any')

    def test_gpa_scales_are_not_converted(self):
        result = self.profile('평점 3.0/4.5(2.8/4.3) 이상')
        self.assertEqual(result['gpa_minima'], {'4.5': 3.0, '4.3': 2.8})
        self.assertEqual(self.profile('평점평균 3.5 이상')['field_states']['gpa'], 'ambiguous')

    def test_complex_curriculum_and_age(self):
        self.assertEqual(self.profile('4년제 2학년, 6년제 4학년 재학생')['field_states']['studentYear'], 'ambiguous')
        result = self.profile('만 19세 이상 35세 이하 성인')
        self.assertEqual((result['age_min'], result['age_max']), (19, 35))
        self.assertEqual(self.profile('공지사항 참조')['field_states']['studentYear'], 'unknown')


if __name__ == '__main__': unittest.main()
