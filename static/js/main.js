// Автоподача фильтров и интерактивность анкеты.
// Вся основная логика сайта выполняется на сервере Flask, поэтому JS остаётся минимальным.

(function () {
  // 1) Автоподача формы фильтров при смене категории или статуса.
  const filterForm = document.querySelector('.filters');
  if (filterForm) {
    filterForm.querySelectorAll('select').forEach((select) => {
      select.addEventListener('change', () => filterForm.submit());
    });
  }

  // 2) Анкета: прогресс заполнения, связь вопросов о курсе и баллах ЕГЭ, проверка чекбоксов.
  const quizForm = document.querySelector('.quiz-form');
  if (quizForm) {
    const progress = document.getElementById('quiz-progress');
    const progressFill = document.getElementById('quiz-progress-fill');
    const progressText = document.getElementById('quiz-progress-text');
    const total = progress ? Number(progress.dataset.total || 0) : 0;

    function countAnsweredRequired() {
      let answered = 0;
      quizForm.querySelectorAll('.question-block[data-required="true"]').forEach((block) => {
        if (block.dataset.type === 'multi') {
          if (block.querySelectorAll('input:checked').length > 0) answered++;
        } else if (block.querySelector('input:checked')) {
          answered++;
        }
      });
      return answered;
    }

    function updateProgress() {
      if (!progress) return;
      const answered = countAnsweredRequired();
      const percent = total > 0 ? Math.round((answered / total) * 100) : 0;
      progressFill.style.width = percent + '%';
      progressText.textContent = `Заполнено обязательных вопросов: ${answered} из ${total}`;
    }

    // Синхронизация вопроса о баллах ЕГЭ с выбранным курсом.
    const courseInputs = quizForm.querySelectorAll('input[name="course"]');
    const notFirstOption = quizForm.querySelector('input[name="ege"][value="not_first"]');

    function currentCourseValue() {
      const checked = quizForm.querySelector('input[name="course"]:checked');
      return checked ? checked.value : null;
    }

    function syncEgeFromCourse() {
      if (!notFirstOption) return;
      const course = currentCourseValue();
      const anyEgeChecked = quizForm.querySelector('input[name="ege"]:checked');

      if (course && course !== 'first' && !anyEgeChecked) {
        notFirstOption.checked = true;
      } else if (course === 'first' && notFirstOption.checked) {
        notFirstOption.checked = false;
      }
      updateProgress();
    }

    if (courseInputs.length) {
      courseInputs.forEach((input) => input.addEventListener('change', syncEgeFromCourse));
    }

    quizForm.addEventListener('change', updateProgress);

    // Перед отправкой подсвечиваем незаполненные обязательные вопросы (особенно checkbox-группы).
    quizForm.addEventListener('submit', (event) => {
      let firstInvalid = null;
      quizForm.querySelectorAll('.question-block[data-required="true"]').forEach((block) => {
        let empty = false;
        if (block.dataset.type === 'multi') {
          empty = block.querySelectorAll('input:checked').length === 0;
        } else {
          empty = !block.querySelector('input:checked');
        }

        if (empty) {
          block.classList.add('is-invalid');
          if (!firstInvalid) firstInvalid = block;
        } else {
          block.classList.remove('is-invalid');
        }
      });

      if (firstInvalid) {
        event.preventDefault();
        firstInvalid.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    });

    updateProgress();
    syncEgeFromCourse();
  }
})();
