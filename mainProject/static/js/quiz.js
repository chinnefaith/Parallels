(() => {
	const app = document.getElementById('quiz-app');
	if (!app) return;

	const loading = document.getElementById('quiz-loading');
	const errorView = document.getElementById('quiz-error-view');
	const errorMessage = document.getElementById('quiz-error');
	const game = document.getElementById('quiz-game');
	const results = document.getElementById('quiz-results');
	const quizTitle = document.getElementById('quiz-title');
	const retryButton = document.getElementById('quiz-retry');
	const scoreLabel = document.getElementById('quiz-score');
	const progress = document.getElementById('quiz-progress');
	const progressLabel = document.getElementById('quiz-progress-label');
	const questionNumber = document.getElementById('quiz-question-number');
	const questionPrompt = document.getElementById('quiz-question');
	const quizContent = document.getElementById('quiz-content');
	const questionArt = document.getElementById('quiz-question-art');
	const questionImage = document.getElementById('quiz-question-image');
	const artPlaceholder = questionArt.querySelector('.quiz-art-placeholder');
	const artCaption = document.getElementById('quiz-art-caption');
	const choices = document.getElementById('quiz-choices');
	const feedback = document.getElementById('quiz-feedback');
	const response = document.getElementById('quiz-response');
	const responseIcon = document.getElementById('quiz-response-icon');
	const responseText = document.getElementById('quiz-response-text');
	const hintButton = document.getElementById('quiz-hint');
	const hintText = document.getElementById('quiz-hint-text');
	const nextButton = document.getElementById('quiz-next');
	const finalScore = document.getElementById('quiz-final-score');
	const resultMessage = document.getElementById('quiz-result-message');
	const restartButton = document.getElementById('quiz-restart');

	const quizLength = 10;
	let categories = [];
	let currentQuestions = [];
	let currentIndex = 0;
	let score = 0;
	let answered = false;

	function showView(view) {
		game.hidden = view !== game;
		results.hidden = view !== results;
		loading.hidden = true;
		errorView.hidden = true;
	}

	function showError(message) {
		loading.hidden = true;
		game.hidden = true;
		results.hidden = true;
		errorMessage.textContent = message;
		errorView.hidden = false;
	}

	function validateQuiz(data) {
		if (!data || !Array.isArray(data.categories) || data.categories.length === 0) {
			throw new Error('The quiz data does not contain any categories.');
		}

		for (const category of data.categories) {
			if (!category.name || !Array.isArray(category.questions)) {
				throw new Error('A quiz category is missing its name or questions.');
			}
			for (const question of category.questions) {
				if (
					!question.question
					|| !Array.isArray(question.choices)
					|| question.choices.length < 2
					|| !Number.isInteger(question.answer_index)
					|| question.answer_index < 0
					|| question.answer_index >= question.choices.length
				) {
					throw new Error(`A question in ${category.name} has invalid quiz data.`);
				}
			}
		}

		return data.categories.filter((category) => category.questions.length > 0);
	}

	function imageUrl(name) {
		const safeName = String(name || '').split('/').pop();
		return safeName ? `${app.dataset.imageBase}${encodeURIComponent(safeName)}` : '';
	}

	function addImageFallback(image, container) {
		image.addEventListener('error', () => {
			container.hidden = true;
		}, { once: true });
	}

	function randomQuestions() {
		const questionPool = categories.flatMap((category) => category.questions.map((question) => ({
			...question,
			categoryName: category.name,
		})));
		for (let index = questionPool.length - 1; index > 0; index -= 1) {
			const randomIndex = Math.floor(Math.random() * (index + 1));
			[questionPool[index], questionPool[randomIndex]] = [
				questionPool[randomIndex],
				questionPool[index],
			];
		}
		return questionPool.slice(0, quizLength);
	}

	function updateProgress(completedQuestions) {
		const progressPercent = Math.round((completedQuestions / quizLength) * 100);
		progress.setAttribute('aria-valuenow', String(completedQuestions));
		progress.replaceChildren();
		for (let index = 0; index < quizLength; index += 1) {
			const segment = document.createElement('span');
			segment.className = 'quiz-progress-segment';
			if (index < completedQuestions) segment.classList.add('is-complete');
			else if (index === currentIndex) segment.classList.add('is-current');
			progress.append(segment);
		}
		progressLabel.textContent = `${progressPercent}% complete`;
	}

	function startQuiz() {
		currentQuestions = randomQuestions();
		currentIndex = 0;
		score = 0;
		answered = false;
		showView(game);
		renderQuestion();
	}

	function renderQuestion() {
		const question = currentQuestions[currentIndex];
		answered = false;
		quizTitle.textContent = question.categoryName;
		scoreLabel.textContent = `Score ${score}`;
		questionNumber.textContent = `Question ${currentIndex + 1} of ${currentQuestions.length}`;
		artCaption.textContent = `Photo for question ${currentIndex + 1}`;
		questionPrompt.textContent = question.question;
		questionPrompt.focus();

		updateProgress(currentIndex);

		const questionImageName = question.question_image_name
			|| question.question_image_path?.split('/').pop();
		const hasFourImageChoices = question.choices.length === 4
			&& question.choices.every((choice) => (
				typeof choice === 'object' && Boolean(choice.image_name)
			));
		quizContent.classList.toggle('has-four-image-choices', hasFourImageChoices);
		choices.classList.toggle('is-image-grid', hasFourImageChoices);
		questionArt.hidden = hasFourImageChoices;

		if (questionImageName && !hasFourImageChoices) {
			questionImage.alt = `Illustration for: ${question.question}`;
			questionImage.hidden = true;
			artPlaceholder.hidden = false;
			questionImage.onload = () => {
				questionImage.hidden = false;
				artPlaceholder.hidden = true;
			};
			questionImage.onerror = () => {
				questionImage.hidden = true;
				artPlaceholder.hidden = false;
			};
			questionImage.src = imageUrl(questionImageName);
		} else {
			questionImage.removeAttribute('src');
			questionImage.hidden = true;
			artPlaceholder.hidden = hasFourImageChoices;
		}

		choices.replaceChildren();
		feedback.textContent = '';
		feedback.className = 'quiz-feedback';
		response.hidden = true;
		response.className = 'quiz-response';
		responseIcon.textContent = '';
		responseText.textContent = '';
		hintText.textContent = '';
		hintText.hidden = true;
		hintButton.disabled = false;
		hintButton.setAttribute('aria-expanded', 'false');
		nextButton.disabled = true;
		nextButton.textContent = currentIndex === currentQuestions.length - 1
			? 'See results'
			: 'Next question';

		question.choices.forEach((choice, index) => {
			const choiceButton = document.createElement('button');
			choiceButton.type = 'button';
			choiceButton.className = 'quiz-choice';
			choiceButton.dataset.choiceIndex = String(index);

			const letter = document.createElement('span');
			letter.className = 'quiz-choice-letter';
			letter.textContent = typeof choice === 'object'
				? choice.label || String.fromCharCode(65 + index)
				: String.fromCharCode(65 + index);
			choiceButton.append(letter);

			if (typeof choice === 'object' && choice.image_name) {
				const art = document.createElement('span');
				art.className = 'quiz-choice-art';
				const image = document.createElement('img');
				image.src = imageUrl(choice.image_name);
				image.alt = choice.alt_text || choice.image_name;
				addImageFallback(image, art);
				art.append(image);
				choiceButton.append(art);
			}

			const text = document.createElement('span');
			text.className = 'quiz-choice-text';
			text.textContent = typeof choice === 'object'
				? choice.text || choice.alt_text || choice.image_name || ''
				: String(choice);
			choiceButton.append(text);
			choiceButton.addEventListener('click', () => selectAnswer(index));
			choices.append(choiceButton);
		});
	}

	function selectAnswer(selectedIndex) {
		if (answered) return;
		answered = true;
		const question = currentQuestions[currentIndex];
		const correct = selectedIndex === question.answer_index;
		if (correct) score += 1;
		updateProgress(currentIndex + 1);
		hintButton.disabled = true;

		choices.querySelectorAll('.quiz-choice').forEach((button, index) => {
			button.disabled = true;
			if (index === question.answer_index) button.classList.add('is-correct');
			if (index === selectedIndex && !correct) button.classList.add('is-incorrect');
		});

		feedback.classList.add(correct ? 'is-correct' : 'is-incorrect');
		feedback.textContent = correct
			? "That's right!"
			: `Not quite. The correct answer is ${choices.children[question.answer_index].querySelector('.quiz-choice-text').textContent}.`;
		response.classList.add(correct ? 'is-correct' : 'is-incorrect');
		responseIcon.textContent = correct ? '✓' : '✕';
		responseText.textContent = correct ? 'Correct!' : 'Not quite!';
		response.hidden = false;
		requestAnimationFrame(() => response.classList.add('is-visible'));
		scoreLabel.textContent = `Score ${score}`;
		nextButton.disabled = false;
		nextButton.focus();
	}

	function showResults() {
		const percentage = Math.round((score / currentQuestions.length) * 100);
		finalScore.textContent = `${score} / ${currentQuestions.length}`;
		resultMessage.textContent = `${percentage}% correct — ${
			percentage === 100
				? 'a perfect score. Excellent shell knowledge!'
				: percentage >= 70
					? 'great work. Keep exploring the shell collection!'
					: 'keep learning. You can try again or choose another topic.'
		}`;
		showView(results);
		document.getElementById('quiz-results-title').focus();
	}

	retryButton.addEventListener('click', loadQuiz);
	nextButton.addEventListener('click', () => {
		if (!answered) return;
		if (currentIndex === currentQuestions.length - 1) {
			showResults();
			return;
		}
		currentIndex += 1;
		renderQuestion();
	});
	restartButton.addEventListener('click', startQuiz);
	hintButton.addEventListener('click', () => {
		const question = currentQuestions[currentIndex];
		hintText.textContent = question.hint || (
			question.type === 'image_choice'
				? 'Compare the shells’ shapes, colors, and surface patterns.'
				: 'Look for the key clue in the question and connect it to the topic.'
		);
		hintText.hidden = false;
		hintButton.setAttribute('aria-expanded', 'true');
	});

	async function loadQuiz() {
		loading.hidden = false;
		errorView.hidden = true;
		game.hidden = true;
		results.hidden = true;
		try {
			const response = await fetch(app.dataset.quizUrl);
			if (!response.ok) {
				throw new Error(`Quiz data request failed (${response.status}).`);
			}
			const data = await response.json();
			categories = validateQuiz(data);
			const questionTotal = categories.reduce(
				(total, category) => total + category.questions.length,
				0,
			);
			if (questionTotal < quizLength) {
				throw new Error(`The quiz needs at least ${quizLength} questions to start.`);
			}
			if (data.quiz_title) quizTitle.textContent = data.quiz_title;
			startQuiz();
		} catch (error) {
			showError(`Unable to load the quiz. ${error.message}`);
		}
	}

	loadQuiz();
})();
