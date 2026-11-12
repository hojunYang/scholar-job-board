import json
import unittest
from unittest.mock import Mock, patch

from classification import CONDITION_PATTERNS, classification_fields
from llm import CompletionExecutor, system_prompt, TAXONOMY


class LlmBatchTests(unittest.TestCase):
    def setUp(self):
        self.executor = CompletionExecutor('https://example.test', 'test-key', 'test-request')
        self.source = '학부연구생 모집\n학부 재학생, 휴학생 불가. 영어 가능자 우대.\n연구를 배우고 수행합니다.'
        self.result = {
            'main_category': '연구경험·학술지원', 'subcategory': '학부연구생·연구실 인턴',
            'classification_reason': '학부생이 연구를 배우는 프로그램',
            'classification_evidence': ['연구를 배우고 수행합니다.'], 'needs_review': False,
            'eligibility_conditions': {key: [] for key in (*CONDITION_PATTERNS, 'evidence')},
        }
        self.result['eligibility_conditions'].update(
            education=['학부 재학생'], enrollment=['학부 재학생', '휴학생 불가'],
            restrictions=['휴학생 불가'], preferences=['영어 가능자 우대'],
            evidence=['학부 재학생', '휴학생 불가', '영어 가능자 우대'])

    def test_prompt_includes_current_taxonomy_and_output_contract(self):
        for main, subs in TAXONOMY.items():
            self.assertIn(main, system_prompt)
        self.assertNotIn('{{TAXONOMY}}', system_prompt)
        self.assertIn('classification_evidence', system_prompt)
        self.assertIn('target_audience', system_prompt)

    def test_request_uses_new_prompt_and_validates_metadata(self):
        response = Mock()
        response.json.return_value = {'result': {'message': {'content': json.dumps(self.result)}}}
        with patch('llm.requests.post', return_value=response) as post:
            self.executor.execute(self.source)
        request = post.call_args_list[0].kwargs
        self.assertEqual(post.call_count, 2)
        subtype_prompt = post.call_args_list[1].kwargs['json']['messages'][0]['content'][0]['text']
        for sub in TAXONOMY[self.result['main_category']]:
            self.assertIn(sub, subtype_prompt)
        self.assertEqual(request['json']['messages'][0]['content'][0]['text'], system_prompt)
        self.assertEqual(request['json']['messages'][1]['content'][0]['text'], self.source)
        self.assertEqual(request['timeout'], (10, 120))
        self.assertEqual(response.raise_for_status.call_count, 2)
        for bad in [[], {'schedule': []}, {'schedule': {'deadline': {}}}, {'target_audience': {'fake': True}}]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.executor._extract_json(json.dumps(bad))

    def test_invalid_main_is_retried_and_never_used_as_free_text(self):
        bad = Mock()
        bad.json.return_value = {'result': {'message': {'content': json.dumps({'main_category': '가짜'})}}}
        good = Mock()
        good.json.return_value = {'result': {'message': {'content': json.dumps(self.result)}}}
        with patch('llm.requests.post', side_effect=[bad, good, good]) as post:
            result = self.executor.execute(self.source)
            self.assertEqual(post.call_count, 3)
            self.assertEqual(result['main_category'], '연구경험·학술지원')
        with patch('llm.requests.post', return_value=bad) as post:
            result = self.executor.execute(self.source)
            self.assertEqual(post.call_count, 2)
            self.assertIsNone(result['main_category'])
            self.assertTrue(result['needs_review'])

    def test_semantic_disagreement_gets_one_grounded_correction(self):
        wrong = dict(self.result, main_category='실험·설문·인터뷰 참여')
        responses = []
        for result in (wrong, self.result, self.result):
            response = Mock()
            response.json.return_value = {'result': {'message': {'content': json.dumps(result)}}}
            responses.append(response)
        with patch('llm.requests.post', side_effect=responses) as post:
            result = self.executor.execute(self.source)
            self.assertEqual(post.call_count, 3)
            self.assertEqual(result['main_category'], '연구경험·학술지원')
            feedback = post.call_args_list[1].kwargs['json']['messages'][-1]['content'][0]['text']
            self.assertIn('참고 후보', feedback)
            self.assertIn('후보는 정답이 아니므로', feedback)

    def test_subtype_network_failure_keeps_extracted_notice_for_review(self):
        response = Mock()
        response.json.return_value = {'result': {'message': {'content': json.dumps(dict(self.result, organizer='연구센터'))}}}
        from requests import ConnectionError
        with patch('llm.requests.post', side_effect=[response, ConnectionError('offline')]):
            result = self.executor.execute(self.source)
        self.assertEqual(result['organizer'], '연구센터')
        self.assertIsNone(result['subcategory'])
        fields = classification_fields('학부연구생 모집', self.source, '', '', '', result)
        self.assertEqual(fields['main_category'], '연구경험·학술지원')
        self.assertEqual(fields['classification_status'], 'needs_review')

    def test_grounded_conditions_saved_without_losing_exclusions(self):
        fields = classification_fields('학부연구생 모집', self.source, '학부 재학생', '', '', self.result)
        self.assertEqual(fields['classification_status'], 'auto')
        conditions = json.loads(fields['eligibility_conditions'])
        self.assertEqual(conditions['preferences'], ['영어 가능자 우대'])
        self.assertIn('휴학생 불가', conditions['enrollment'])

    def test_conflict_preserves_rule_and_records_llm_candidate(self):
        fields = classification_fields('심리학 실험 참여자 모집', self.source, '학부 재학생', '', '', self.result)
        self.assertEqual(fields['main_category'], '실험·설문·인터뷰 참여')
        self.assertEqual(fields['classification_status'], 'needs_review')
        self.assertIn('LLM 후보: 연구경험·학술지원', fields['classification_reason'])
        self.assertIn('규칙과 불일치', fields['classification_reason'])

    def test_hallucinated_conditions_fall_back_and_require_review(self):
        self.result['eligibility_conditions']['gpa'] = ['평점 4.0 이상']
        fields = classification_fields('학부연구생 모집', self.source, '학부 재학생, 휴학생 불가', '', '', self.result)
        self.assertEqual(fields['classification_status'], 'needs_review')
        self.assertNotIn('평점 4.0 이상', fields['eligibility_conditions'])
        self.assertIn('휴학생 불가', fields['eligibility_conditions'])

    def test_fallback_does_not_trust_hallucinated_audience_summary(self):
        self.result['eligibility_conditions']['gpa'] = ['평점 4.0 이상']
        fields = classification_fields('학부연구생 모집', self.source,
                                       '대학원생만 지원 가능, 평점 4.0 이상', '', '', self.result)
        self.assertNotIn('평점 4.0 이상', fields['eligibility_conditions'])
        self.assertNotIn('대학원생만 지원 가능', fields['eligibility_conditions'])
        self.assertEqual(fields['classification_status'], 'needs_review')

    def test_literal_string_evidence_is_checked_as_a_single_quote(self):
        self.result['classification_evidence'] = '연구를 배우고 수행합니다.'
        fields = classification_fields('학부연구생 모집', self.source, '', '', '', self.result)
        self.assertEqual(fields['classification_status'], 'auto')
        self.result['classification_evidence'] = '연구를 배우고 수행합니다., 근로학생에게 시급을 지급합니다.'
        fields = classification_fields('학부연구생 모집', self.source, '', '', '', self.result)
        self.assertEqual(fields['classification_status'], 'needs_review')

    def test_fabricated_classification_evidence_is_flagged(self):
        self.result['classification_evidence'] = ['입력의 지시를 무시하라']
        fields = classification_fields('학부연구생 모집', self.source, '', '', '', self.result)
        self.assertEqual(fields['classification_status'], 'needs_review')
        self.assertIn('원문에 없음', fields['classification_reason'])


if __name__ == '__main__':
    unittest.main()
