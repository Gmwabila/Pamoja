
document.querySelectorAll('[data-password]').forEach(button => {
  button.addEventListener('click', () => {
    const field = document.getElementById(button.dataset.password);

    if (!field) return;

    const visible = field.type === 'password';

    field.type = visible ? 'text' : 'password';

    // Translated labels supplied by form_fields.html.
    button.textContent = visible
      ? (button.dataset.hideText || 'Hide')
      : (button.dataset.showText || 'Show');

    button.setAttribute('aria-pressed', String(visible));

    button.setAttribute(
      'aria-label',
      visible
        ? (button.dataset.hideAria || 'Hide password')
        : (button.dataset.showAria || 'Show password')
    );
  });
});


// Confirmation before deleting a task.
document.querySelectorAll('form[data-confirm]').forEach(form => {
  form.addEventListener('submit', event => {
    if (!window.confirm(form.dataset.confirm)) {
      event.preventDefault();
    }
  });
});


// Suggest the browser's time zone for new users only.
const timezoneSelect = document.getElementById('id_timezone');

if (timezoneSelect && timezoneSelect.value === 'UTC') {
  const onboarding = document.querySelector('.onboarding');

  // Prefer a language-independent marker when available.
  // Retain the existing English-heading check for compatibility.
  const isNew =
    onboarding?.dataset.newOnboarding === 'true' ||
    onboarding?.querySelector('.eyebrow')?.textContent.trim() ===
      'A LITTLE ABOUT YOU';

  const detected = Intl.DateTimeFormat()
    .resolvedOptions()
    .timeZone;

  if (
    isNew &&
    [...timezoneSelect.options].some(
      option => option.value === detected
    )
  ) {
    timezoneSelect.value = detected;
  }
}


// Register the PAMOJA service worker.
if ('serviceWorker' in navigator && window.isSecureContext) {
  navigator.serviceWorker.register('/sw.js').catch(() => {});
}
