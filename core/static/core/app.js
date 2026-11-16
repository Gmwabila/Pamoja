document.querySelectorAll('[data-password]').forEach(button => {
  button.addEventListener('click', () => {
    const field = document.getElementById(button.dataset.password);
    const visible = field.type === 'password';
    field.type = visible ? 'text' : 'password';
    button.textContent = visible ? 'Hide' : 'Show';
    button.setAttribute('aria-pressed', String(visible));
    button.setAttribute('aria-label', (visible ? 'Hide ' : 'Show ') + 'password');
  });
});
document.querySelectorAll('form[data-confirm]').forEach(form => {
  form.addEventListener('submit', event => {
    if (!window.confirm(form.dataset.confirm)) event.preventDefault();
  });
});
const timezoneSelect = document.getElementById('id_timezone');
if (timezoneSelect && timezoneSelect.value === 'UTC') {
  // Suggest the browser zone only for a fresh onboarding form, not saved preferences.
  const isNew = document.querySelector('.onboarding .eyebrow')?.textContent.trim() === 'A LITTLE ABOUT YOU';
  const detected = Intl.DateTimeFormat().resolvedOptions().timeZone;
  if (isNew && [...timezoneSelect.options].some(option => option.value === detected)) timezoneSelect.value = detected;
}
if ('serviceWorker' in navigator && window.isSecureContext) {
  navigator.serviceWorker.register('/sw.js').catch(() => {});
}
