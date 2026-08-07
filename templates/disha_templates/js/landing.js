/**
 * Disha — Exam Selector Landing Page
 *
 * Configuration-driven: to add a new exam, append an object to the EXAMS array.
 * The grid, cards, search, and routing all derive from this single source of truth.
 */

const EXAMS = [
  {
    id: 'jee',
    name: 'JEE / JEE Advanced',
    subtitle: 'For IITs, NITs, IIITs & GFTIs via JoSAA Counselling.',
    stat: '2,410+ cutoff records · All India',
    conductingBody: 'Conducted by NTA',
    conductingBodyUrl: 'https://jeemain.nta.nic.in',
    route: 'exam/jee',
    badge: 'Popular',
    icon: `<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M22 10v6M2 10l10-5 10 5-10 5z"/>
      <path d="M6 12v5c0 1.7 2.7 3 6 3s6-1.3 6-3v-5"/>
    </svg>`
  },
  {
    id: 'kcet',
    name: 'KCET',
    subtitle: 'For Govt. & Private Engineering Colleges in Karnataka.',
    stat: 'Govt & Private · Karnataka only',
    conductingBody: 'Conducted by KEA',
    conductingBodyUrl: 'https://kea.kar.nic.in',
    route: 'exam/kcet',
    badge: 'Karnataka',
    icon: `<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M3 21h18"/>
      <path d="M5 21V7l7-4 7 4v14"/>
      <path d="M9 21v-6h6v6"/>
      <path d="M10 10h.01M14 10h.01"/>
    </svg>`
  },
  {
    id: 'comedk',
    name: 'COMEDK',
    subtitle: 'For Private Engineering Colleges across Karnataka — All India eligible.',
    stat: 'Private colleges · All India eligible',
    conductingBody: 'Conducted by COMEDK',
    conductingBodyUrl: 'https://www.comedk.org',
    route: 'exam/comedk',
    badge: 'All India',
    icon: `<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <rect x="2" y="3" width="20" height="14" rx="2" ry="2"/>
      <path d="M8 21h8"/>
      <path d="M12 17v4"/>
      <path d="M7 8h2m2 0h2m2 0h2"/>
      <path d="M7 12h10"/>
    </svg>`
  }
];


/* ── Card renderer ───────────────────────────────────────────────── */

function createExamCard(exam) {
  return `
    <a href="${exam.route}" class="exam-card"
       aria-label="Go to ${exam.name}">

      ${exam.badge ? `<span class="exam-card__badge">${exam.badge}</span>` : ''}

      <div class="exam-card__icon" aria-hidden="true">
        ${exam.icon}
      </div>

      <h2 class="exam-card__title">${exam.name}</h2>
      <p class="exam-card__desc">${exam.subtitle}</p>

      <div class="exam-card__stat">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
        </svg>
        ${exam.stat}
      </div>

      <span class="exam-card__spacer"></span>

      <p class="exam-card__conductor">
        ${exam.conductingBody} ·
        <span onclick="event.stopPropagation(); window.open('${exam.conductingBodyUrl}', '_blank')">Official site ↗</span>
      </p>

      <span class="exam-card__cta">
        Explore
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">
          <path d="M5 12h14M13 6l6 6-6 6"/>
        </svg>
      </span>
    </a>
  `;
}


/* ── Render + search logic ───────────────────────────────────────── */

function renderExams(filter = '') {
  const container = document.getElementById('exam-grid-container');
  if (!container) return;

  const query = filter.trim().toLowerCase();
  const matched = EXAMS.filter(e =>
    !query ||
    e.name.toLowerCase().includes(query) ||
    e.subtitle.toLowerCase().includes(query) ||
    e.stat.toLowerCase().includes(query) ||
    e.conductingBody.toLowerCase().includes(query) ||
    (e.badge && e.badge.toLowerCase().includes(query))
  );

  if (matched.length === 0) {
    container.innerHTML = `
      <div class="exam-grid">
        <div class="exam-empty">
          <div class="exam-empty__icon">🔍</div>
          <p class="exam-empty__text">No matching exam found. Try a different keyword.</p>
        </div>
      </div>
    `;
    return;
  }

  container.innerHTML = `
    <div class="exam-grid">
      ${matched.map(e => createExamCard(e)).join('')}
    </div>
  `;
}

document.addEventListener('DOMContentLoaded', () => {
  renderExams();

  const searchInput = document.getElementById('exam-search');
  if (searchInput) {
    searchInput.addEventListener('input', () => renderExams(searchInput.value));
  }
});
