import io
import tempfile
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from museum.models import Era, Topic, Card, CardProgress, validate_image
from museum.views import era_rows
from .models import Quiz, Question, Choice, QuizAttempt, AttemptAnswer
from .services import submit_attempt, total_score, visible_quizzes

class MuseumAcceptanceTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.media = tempfile.TemporaryDirectory()
        cls.media_settings = override_settings(MEDIA_ROOT=__import__('pathlib').Path(cls.media.name))
        cls.media_settings.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.media_settings.disable()
        cls.media.cleanup()

    @classmethod
    def setUpTestData(cls):
        call_command('seed_demo', stdout=io.StringIO())
        cls.user = get_user_model().objects.create_user('student_test', password='Museum_test_6284')
        cls.other = get_user_model().objects.create_user('another_test', password='Museum_test_6284')
        cls.quiz = Quiz.objects.filter(kind='final').first()
        cls.mini = Quiz.objects.filter(kind='mini').first()
        cls.card = Card.objects.first()

    def setUp(self): self.client.force_login(self.user)

    def payload(self, quiz, correct_count):
        return {f'question_{q.pk}': str(q.choices.filter(correct=i < correct_count).first().pk) for i, q in enumerate(quiz.questions.all())}

    def play(self, quiz, correct_count):
        attempt = QuizAttempt.objects.create(quiz=quiz, user=self.user)
        return submit_attempt(attempt.pk, self.user, self.payload(quiz, correct_count))

    def test_k1_initial_content_and_guest_access(self):
        self.client.logout()
        self.assertEqual((Era.objects.count(), Topic.objects.count(), Card.objects.count(), Question.objects.count()), (3, 9, 36, 24))
        self.assertEqual(Quiz.objects.filter(kind='mini').count(), 9)
        self.assertEqual(Quiz.objects.filter(kind='final').count(), 3)
        for url in ['/', '/eras/', '/cards/', '/quizzes/', '/sources/', f'/topics/{self.card.topic_id}/', f'/cards/{self.card.pk}/']:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.assertRedirects(self.client.get(f'/quizzes/{self.quiz.pk}/'), f'/accounts/login/?next=/quizzes/{self.quiz.pk}/')

    def test_k2_filters_search_together_and_empty_state(self):
        response = self.client.get('/cards/', {'era': self.card.topic.era.slug, 'type': self.card.type, 'q': self.card.title.upper()})
        self.assertEqual(list(response.context['cards']), [self.card])
        self.assertContains(self.client.get('/cards/', {'q': 'неттакогоматериала'}), 'Ничего не найдено')

    def test_k3_registration_and_login_persist_progress(self):
        self.client.logout()
        response = self.client.post('/accounts/register/', {'username': 'new_student', 'password1': 'Fresh_Museum_314159', 'password2': 'Fresh_Museum_314159'})
        self.assertRedirects(response, '/profile/')
        user = get_user_model().objects.get(username='new_student')
        self.assertTrue(user.check_password('Fresh_Museum_314159'))
        self.client.post(f'/cards/{self.card.pk}/progress/', {'action': 'mark'})
        self.client.post('/accounts/logout/')
        self.assertTrue(self.client.login(username='new_student', password='Fresh_Museum_314159'))
        self.assertContains(self.client.get('/profile/'), self.card.title)
        self.assertTrue(CardProgress.objects.filter(user=user, card=self.card).exists())

    def test_k4_marking_is_idempotent_and_reversible(self):
        url = f'/cards/{self.card.pk}/progress/'
        self.assertEqual(self.client.get(url).status_code, 405)
        for _ in range(2): self.client.post(url, {'action': 'mark'})
        self.assertEqual(CardProgress.objects.filter(user=self.user, card=self.card).count(), 1)
        row = next(r for r in era_rows(self.user) if r['era'].pk == self.card.topic.era_id)
        self.assertEqual(row['percent'], 8)
        for _ in range(2): self.client.post(url, {'action': 'unmark'})
        self.assertFalse(CardProgress.objects.filter(user=self.user).exists())
        self.assertEqual(total_score(self.user), 0)

    def test_k5_mini_scoring(self):
        wrong = self.play(self.mini, 0)
        right = self.play(self.mini, 1)
        self.assertEqual((wrong.points, right.points, total_score(self.user)), (0, 5, 5))
        self.assertContains(self.client.get(f'/attempts/{right.pk}/'), self.mini.questions.first().explanation)

    def test_k6_three_of_five(self):
        attempt = self.play(self.quiz, 3)
        self.assertEqual((attempt.correct_count, attempt.points), (3, 30))
        response = self.client.get(f'/attempts/{attempt.pk}/')
        self.assertContains(response, '3 / 5')
        self.assertContains(response, '60%')
        self.assertEqual(len(response.context['review']), 5)

    def test_k7_best_result_not_sum(self):
        for count in [2, 4, 3]: self.play(self.quiz, count)
        self.assertEqual(QuizAttempt.objects.filter(user=self.user, status='completed').count(), 3)
        self.assertEqual(total_score(self.user), 40)

    def test_k8_repeated_submission_returns_same_result(self):
        attempt = self.play(self.quiz, 3)
        again = submit_attempt(attempt.pk, self.user, self.payload(self.quiz, 5))
        self.assertEqual((again.points, again.correct_count), (30, 3))
        self.assertEqual(AttemptAnswer.objects.filter(attempt=attempt).count(), 5)
        self.assertEqual(QuizAttempt.objects.filter(user=self.user).count(), 1)

    def test_k9_other_users_attempt_is_hidden(self):
        attempt = QuizAttempt.objects.create(user=self.other, quiz=self.quiz)
        for url in [f'/attempts/{attempt.pk}/', f'/attempts/{attempt.pk}/submit/']:
            response = self.client.get(url) if url.endswith(f'{attempt.pk}/') else self.client.post(url, self.payload(self.quiz, 5))
            self.assertEqual(response.status_code, 404)

    def test_k9_injected_choice_rejected_atomically(self):
        attempt = QuizAttempt.objects.create(user=self.user, quiz=self.quiz)
        payload = self.payload(self.quiz, 5)
        question = self.quiz.questions.first()
        payload[f'question_{question.pk}'] = self.mini.questions.first().choices.first().pk
        response = self.client.post(f'/attempts/{attempt.pk}/submit/', payload)
        self.assertEqual(response.status_code, 400)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, 'started')
        self.assertEqual(attempt.answers.count(), 0)
        self.assertEqual(total_score(self.user), 0)

    def test_incomplete_attempt_has_no_score(self):
        attempt = QuizAttempt.objects.create(user=self.user, quiz=self.quiz)
        payload = self.payload(self.quiz, 5)
        payload.pop(next(iter(payload)))
        self.assertEqual(self.client.post(f'/attempts/{attempt.pk}/submit/', payload).status_code, 400)
        self.assertEqual(attempt.answers.count(), 0)
        self.assertEqual(total_score(self.user), 0)

    def test_client_supplied_score_is_ignored(self):
        attempt = QuizAttempt.objects.create(user=self.user, quiz=self.quiz)
        payload = self.payload(self.quiz, 0) | {'points': '9999', 'correct_count': '5', 'status': 'completed'}
        self.client.post(f'/attempts/{attempt.pk}/submit/', payload)
        attempt.refresh_from_db()
        self.assertEqual(attempt.points, 0)

    def test_answers_not_leaked_before_submission(self):
        attempt = QuizAttempt.objects.create(user=self.user, quiz=self.quiz)
        response = self.client.get(f'/attempts/{attempt.pk}/')
        for question in self.quiz.questions.all(): self.assertNotContains(response, question.explanation)
        for question in response.context['questions']:
            self.assertNotIn('explanation', question)
            for choice in question['choices']: self.assertNotIn('correct', choice)

    def test_k10_hidden_parent_hides_all_children(self):
        attempt = QuizAttempt.objects.create(user=self.user, quiz=self.quiz)
        era = self.quiz.era
        era.published = False
        era.save()
        card = Card.objects.filter(topic__era=era).first()
        for url in [f'/eras/{era.slug}/', f'/topics/{card.topic_id}/', f'/cards/{card.pk}/', f'/quizzes/{self.quiz.pk}/', f'/attempts/{attempt.pk}/']:
            self.assertEqual(self.client.get(url).status_code, 404, url)
        self.assertNotContains(self.client.get('/cards/'), card.title)

    def test_hidden_topic_hides_card_and_mini(self):
        topic = self.mini.topic
        topic.published = False
        topic.save()
        card = topic.cards.first()
        for url in [f'/topics/{topic.pk}/', f'/cards/{card.pk}/', f'/quizzes/{self.mini.pk}/']:
            self.assertEqual(self.client.get(url).status_code, 404)

    def test_hidden_card_direct_link(self):
        topic = self.card.topic
        topic.published = False
        topic.save()
        self.card.published = False
        self.card.save()
        self.assertEqual(self.client.get(f'/cards/{self.card.pk}/').status_code, 404)

    def test_k11_incomplete_quiz_and_question_publication(self):
        quiz = Quiz.objects.create(era=self.quiz.era, kind='final', title='Черновик')
        quiz.published = True
        with self.assertRaisesMessage(ValidationError, '5'): quiz.save()
        quiz.published = False
        quiz.save()
        for i in range(5):
            question = Question.objects.create(quiz=quiz, text=f'Вопрос {i}', explanation='')
            for j in range(4): Choice.objects.create(question=question, text=f'Вариант {j}', correct=j==0)
        quiz.published = True
        with self.assertRaises(ValidationError): quiz.save()

    def test_valid_quiz_publishes(self):
        original = self.quiz
        original.published = False
        original.save()
        quiz = Quiz.objects.create(era=original.era, kind='final', title='Новая версия', version=2)
        for i in range(5):
            q = Question.objects.create(quiz=quiz, text=f'Вопрос {i}', explanation='Пояснение')
            for j in range(4): Choice.objects.create(question=q, text=f'Вариант {j}', correct=j==0)
        quiz.published = True
        quiz.save()
        self.assertTrue(visible_quizzes().filter(pk=quiz.pk).exists())

    def test_topic_publication_requires_complete_set(self):
        topic = Topic.objects.create(era=self.quiz.era, title='Неполная тема', slug='empty', description='Описание')
        topic.published = True
        with self.assertRaisesMessage(ValidationError, 'четыре'): topic.save()

    def test_k12_all_correct_maximum_195(self):
        for quiz in visible_quizzes():
            self.play(quiz, quiz.questions.count())
            self.play(quiz, quiz.questions.count())
        self.assertEqual(total_score(self.user), 195)
        self.assertEqual(QuizAttempt.objects.filter(user=self.user, status='completed').count(), 24)

    def test_k14_seed_is_idempotent_and_preserves_results(self):
        attempt = self.play(self.quiz, 3)
        card_title = self.card.title
        self.card.title = 'Название, изменённое администратором'
        self.card.save()
        era = self.quiz.era
        era.published = False
        era.save()
        call_command('seed_demo', stdout=io.StringIO())
        self.assertEqual((Era.objects.count(), Topic.objects.count(), Card.objects.count(), Quiz.objects.count(), Question.objects.count()), (3, 9, 36, 12, 24))
        self.assertEqual(QuizAttempt.objects.get(pk=attempt.pk).points, 30)
        self.assertEqual(Card.objects.get(pk=self.card.pk).title, self.card.title)
        self.assertFalse(Era.objects.get(pk=era.pk).published)

    def test_unpublished_quiz_excluded_score_history_retained(self):
        self.play(self.quiz, 4)
        self.quiz.published = False
        self.quiz.save()
        self.assertEqual(total_score(self.user), 0)
        self.assertEqual(self.user.attempts.count(), 1)
        self.assertEqual(self.client.get(f'/attempts/{self.user.attempts.first().pk}/').status_code, 200)

    def test_quiz_with_attempt_cannot_be_edited_or_deleted(self):
        self.play(self.quiz, 3)
        self.quiz.title = 'Подмена'
        with self.assertRaises(ValidationError): self.quiz.save()
        question = self.quiz.questions.first()
        question.text = 'Подмена'
        with self.assertRaises(ValidationError): question.save()
        choice = question.choices.first()
        choice.correct = not choice.correct
        with self.assertRaises(ValidationError): choice.save()
        with self.assertRaises(ProtectedError): self.quiz.delete()

    def test_unique_public_quiz_constraint(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Quiz.objects.bulk_create([Quiz(era=self.quiz.era, title='Дубликат', kind='final', published=True)])

    def test_foreign_topic_era_validation(self):
        quiz = Quiz(era=Era.objects.exclude(pk=self.mini.era_id).first(), topic=self.mini.topic, kind='mini', title='Не та эпоха')
        with self.assertRaises(ValidationError): quiz.save()

    def test_csrf_for_mutation_and_staff_admin(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        self.assertEqual(csrf_client.post(f'/cards/{self.card.pk}/progress/', {'action': 'mark'}).status_code, 403)
        self.assertEqual(self.client.get('/admin/').status_code, 302)

    def test_images_validated_and_all_cards_have_assets(self):
        fake = SimpleUploadedFile('fake.png', b'<script>not an image</script>', content_type='image/png')
        with self.assertRaises(ValidationError): validate_image(fake)
        huge = SimpleUploadedFile('large.png', b'x' * (5 * 1024 * 1024 + 1))
        with self.assertRaises(ValidationError): validate_image(huge)
        for card in Card.objects.all():
            self.assertTrue(card.image.storage.exists(card.image.name))
            self.assertTrue(card.caption and card.alt and card.source)

    def test_content_length_and_initial_progress(self):
        for card in Card.objects.all():
            self.assertGreaterEqual(len(card.text.split()), 80, card.title)
            self.assertLessEqual(len(card.text.split()), 150, card.title)
        self.assertTrue(all(r['percent'] == 0 for r in era_rows(self.user)))
