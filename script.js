document.addEventListener('DOMContentLoaded', () => {
    // Intersection Observer for fade-in animations
    const observerOptions = {
        root: null,
        rootMargin: '0px',
        threshold: 0.1
    };

    const observer = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
                observer.unobserve(entry.target); // Only animate once
            }
        });
    }, observerOptions);

    const fadeElements = document.querySelectorAll('.fade-in');
    fadeElements.forEach(el => observer.observe(el));

    // Smooth scroll for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth'
                });
            }
        });
    });
    // Contact Form Handler (Mailto fallback)
    const contactForm = document.querySelector('form');
    if (contactForm) {
        contactForm.addEventListener('submit', function (e) {
            e.preventDefault();
            const name = this.querySelector('[name="name"]').value;
            const email = this.querySelector('[name="email"]').value;
            const type = this.querySelector('[name="type"]').value;
            const message = this.querySelector('[name="message"]').value;

            const subject = `New Inquiry from ${name} (${type})`;
            const body = `Name: ${name}\nEmail: ${email}\nType: ${type}\n\nMessage:\n${message}`;

            window.location.href = `mailto:vilgotfjellsten@gmail.com?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
        });
    }
});
