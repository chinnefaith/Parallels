document.querySelectorAll('table tbody tr td:nth-child(4)').forEach((element) => {
  const value = Number(element.textContent.trim());
  if (!Number.isNaN(value)) element.textContent = `${(value * 100).toFixed(1)}%`;
});

document.querySelectorAll('.summary span:nth-child(4) strong').forEach((element) => {
  const value = Number(element.textContent.trim());
  if (!Number.isNaN(value)) element.textContent = `${(value * 100).toFixed(1)}%`;
});

document.querySelectorAll('table tbody tr td:nth-child(6)').forEach((element) => {
  element.textContent = element.textContent.trim().split('@', 1)[0] || '-';
});
