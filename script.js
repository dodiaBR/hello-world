// Navbar scroll effect
const navbar = document.getElementById('navbar');
window.addEventListener('scroll', () => {
  navbar.classList.toggle('scrolled', window.scrollY > 10);
}, { passive: true });

// Mobile menu
const hamburger = document.getElementById('hamburger');
const mobileMenu = document.getElementById('mobileMenu');
hamburger.addEventListener('click', () => {
  const open = mobileMenu.classList.toggle('open');
  hamburger.setAttribute('aria-expanded', open);
});
mobileMenu.querySelectorAll('a').forEach(link => {
  link.addEventListener('click', () => mobileMenu.classList.remove('open'));
});

// ── CAROUSEL ──────────────────────────────────────────────────────────────────
const track    = document.getElementById('carTrack');
const viewport = document.getElementById('carViewport');
const prevBtn  = document.getElementById('prevBtn');
const nextBtn  = document.getElementById('nextBtn');
const dotsWrap = document.getElementById('carDots');
const cards    = Array.from(track.querySelectorAll('.testi-card'));

let idx = 0;
let autoTimer = null;

function visibleCount() {
  const w = window.innerWidth;
  if (w <= 480)  return 1;
  if (w <= 1024) return 2;
  return 3;
}

function maxIdx() { return Math.max(0, cards.length - visibleCount()); }

function cardWidth() {
  if (!cards[0]) return 0;
  const gap = 20;
  return cards[0].offsetWidth + gap;
}

function buildDots() {
  dotsWrap.innerHTML = '';
  for (let i = 0; i <= maxIdx(); i++) {
    const btn = document.createElement('button');
    btn.className = 'car-dot' + (i === idx ? ' active' : '');
    btn.setAttribute('aria-label', `Slide ${i + 1}`);
    btn.addEventListener('click', () => { goTo(i); resetAuto(); });
    dotsWrap.appendChild(btn);
  }
}

function syncDots() {
  dotsWrap.querySelectorAll('.car-dot').forEach((d, i) => {
    d.classList.toggle('active', i === idx);
  });
}

function goTo(i) {
  const max = maxIdx();
  idx = Math.max(0, Math.min(i, max));
  track.style.transform = `translateX(-${idx * cardWidth()}px)`;
  prevBtn.disabled = idx === 0;
  nextBtn.disabled = idx >= max;
  syncDots();
}

function resetAuto() {
  clearInterval(autoTimer);
  autoTimer = setInterval(() => goTo(idx >= maxIdx() ? 0 : idx + 1), 5500);
}

prevBtn.addEventListener('click', () => { goTo(idx - 1); resetAuto(); });
nextBtn.addEventListener('click', () => { goTo(idx + 1); resetAuto(); });

// Touch swipe
let tx = 0;
viewport.addEventListener('touchstart', e => { tx = e.touches[0].clientX; }, { passive: true });
viewport.addEventListener('touchend', e => {
  const diff = tx - e.changedTouches[0].clientX;
  if (Math.abs(diff) > 40) { goTo(diff > 0 ? idx + 1 : idx - 1); resetAuto(); }
});

// Pause on hover
viewport.addEventListener('mouseenter', () => clearInterval(autoTimer));
viewport.addEventListener('mouseleave', resetAuto);

// Re-init on resize
let resizeTimer;
window.addEventListener('resize', () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => {
    buildDots();
    goTo(Math.min(idx, maxIdx()));
  }, 120);
});

function initCarousel() {
  buildDots();
  goTo(0);
  resetAuto();
}
initCarousel();

// ── ENTRANCE ANIMATIONS ────────────────────────────────────────────────────────
const fadeEls = document.querySelectorAll(
  '.level-card, .lesson-card, .plano-card, .recurso-card, .official-link-card'
);
const io = new IntersectionObserver(entries => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.style.opacity = '1';
      entry.target.style.transform = 'translateY(0)';
      io.unobserve(entry.target);
    }
  });
}, { threshold: 0.08, rootMargin: '0px 0px -32px 0px' });

fadeEls.forEach((el, i) => {
  el.style.opacity = '0';
  el.style.transform = 'translateY(16px)';
  el.style.transition = `opacity .4s ease ${(i % 4) * 60}ms, transform .4s ease ${(i % 4) * 60}ms`;
  io.observe(el);
});

// ── SMOOTH SCROLL ─────────────────────────────────────────────────────────────
document.querySelectorAll('a[href^="#"]').forEach(a => {
  a.addEventListener('click', e => {
    const target = document.querySelector(a.getAttribute('href'));
    if (target) {
      e.preventDefault();
      window.scrollTo({ top: target.getBoundingClientRect().top + scrollY - 72, behavior: 'smooth' });
    }
  });
});
