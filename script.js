// Navbar scroll effect
const navbar = document.getElementById('navbar');
window.addEventListener('scroll', () => {
  navbar.classList.toggle('scrolled', window.scrollY > 20);
});

// Mobile menu
const hamburger = document.getElementById('hamburger');
const mobileMenu = document.getElementById('mobileMenu');
hamburger.addEventListener('click', () => {
  mobileMenu.classList.toggle('open');
});
mobileMenu.querySelectorAll('a').forEach(link => {
  link.addEventListener('click', () => mobileMenu.classList.remove('open'));
});

// Pricing toggle
const pricingToggle = document.getElementById('pricingToggle');
const lblMonthly = document.getElementById('lblMonthly');
const lblAnnual  = document.getElementById('lblAnnual');

pricingToggle.addEventListener('change', () => {
  const isAnnual = pricingToggle.checked;
  document.querySelectorAll('.monthly-price').forEach(el => el.style.display = isAnnual ? 'none' : '');
  document.querySelectorAll('.annual-price').forEach(el => el.style.display = isAnnual ? '' : 'none');
  lblMonthly.classList.toggle('active', !isAnnual);
  lblAnnual.classList.toggle('active', isAnnual);
});

// FAQ accordion
document.querySelectorAll('.faq-question').forEach(btn => {
  btn.addEventListener('click', () => {
    const item   = btn.closest('.faq-item');
    const answer = item.querySelector('.faq-answer');
    const isOpen = item.classList.contains('open');

    document.querySelectorAll('.faq-item.open').forEach(openItem => {
      openItem.classList.remove('open');
      openItem.querySelector('.faq-answer').style.maxHeight = null;
    });

    if (!isOpen) {
      item.classList.add('open');
      answer.style.maxHeight = answer.scrollHeight + 'px';
    }
  });
});

// Carousel
const track      = document.getElementById('carouselTrack');
const viewport   = document.getElementById('carouselViewport');
const prevBtn    = document.getElementById('prevBtn');
const nextBtn    = document.getElementById('nextBtn');
const dotsWrap   = document.getElementById('carouselDots');
const cards      = track.querySelectorAll('.testimonial-card');

let currentIndex = 0;
let autoTimer;

function getVisibleCount() {
  const vw = window.innerWidth;
  if (vw <= 480)  return 1;
  if (vw <= 1024) return 2;
  return 3;
}

function getMaxIndex() {
  return Math.max(0, cards.length - getVisibleCount());
}

function buildDots() {
  dotsWrap.innerHTML = '';
  const count = getMaxIndex() + 1;
  for (let i = 0; i < count; i++) {
    const dot = document.createElement('button');
    dot.className = 'carousel-dot' + (i === currentIndex ? ' active' : '');
    dot.setAttribute('aria-label', `Slide ${i + 1}`);
    dot.addEventListener('click', () => goTo(i));
    dotsWrap.appendChild(dot);
  }
}

function updateDots() {
  dotsWrap.querySelectorAll('.carousel-dot').forEach((dot, i) => {
    dot.classList.toggle('active', i === currentIndex);
  });
}

function getCardWidth() {
  if (!cards[0]) return 0;
  const gap = 24;
  return cards[0].offsetWidth + gap;
}

function goTo(index) {
  const max = getMaxIndex();
  currentIndex = Math.max(0, Math.min(index, max));
  track.style.transform = `translateX(-${currentIndex * getCardWidth()}px)`;
  prevBtn.disabled = currentIndex === 0;
  nextBtn.disabled = currentIndex >= max;
  updateDots();
}

function startAuto() {
  stopAuto();
  autoTimer = setInterval(() => {
    const max = getMaxIndex();
    goTo(currentIndex >= max ? 0 : currentIndex + 1);
  }, 5000);
}

function stopAuto() {
  clearInterval(autoTimer);
}

prevBtn.addEventListener('click', () => { goTo(currentIndex - 1); stopAuto(); startAuto(); });
nextBtn.addEventListener('click', () => { goTo(currentIndex + 1); stopAuto(); startAuto(); });

// Touch/swipe support
let touchStartX = 0;
viewport.addEventListener('touchstart', e => { touchStartX = e.touches[0].clientX; }, { passive: true });
viewport.addEventListener('touchend', e => {
  const diff = touchStartX - e.changedTouches[0].clientX;
  if (Math.abs(diff) > 40) {
    goTo(diff > 0 ? currentIndex + 1 : currentIndex - 1);
    stopAuto(); startAuto();
  }
});

// Pause on hover
viewport.addEventListener('mouseenter', stopAuto);
viewport.addEventListener('mouseleave', startAuto);

// Init
function init() {
  buildDots();
  goTo(currentIndex);
  startAuto();
}

window.addEventListener('resize', () => {
  buildDots();
  goTo(Math.min(currentIndex, getMaxIndex()));
});

init();

// Smooth scroll for anchor links
document.querySelectorAll('a[href^="#"]').forEach(link => {
  link.addEventListener('click', e => {
    const target = document.querySelector(link.getAttribute('href'));
    if (target) {
      e.preventDefault();
      const offset = 80;
      const top = target.getBoundingClientRect().top + window.scrollY - offset;
      window.scrollTo({ top, behavior: 'smooth' });
    }
  });
});

// Intersection observer for entrance animations
const observer = new IntersectionObserver(entries => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.style.opacity = '1';
      entry.target.style.transform = 'translateY(0)';
      observer.unobserve(entry.target);
    }
  });
}, { threshold: 0.1 });

document.querySelectorAll('.method-card, .course-card, .pricing-card, .faq-item').forEach(el => {
  el.style.opacity = '0';
  el.style.transform = 'translateY(20px)';
  el.style.transition = 'opacity .5s ease, transform .5s ease';
  observer.observe(el);
});
