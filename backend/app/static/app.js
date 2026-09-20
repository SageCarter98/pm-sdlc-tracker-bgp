// WP11: the one piece of behaviour that genuinely needs JS rather than
// being achievable with plain HTML -- moving keyboard/screen-reader focus
// to the error summary on page load (Blueprint Sec.4.2: "Focus moves to
// validation summaries"). Everything else on these pages (forms, saves,
// navigation) works with JS disabled -- progressive enhancement, not a
// requirement.
document.addEventListener("DOMContentLoaded", () => {
  const summary = document.getElementById("error-summary");
  if (summary) {
    summary.focus();
  }
});
