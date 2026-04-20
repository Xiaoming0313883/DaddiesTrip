document.getElementById('generate-btn').addEventListener('click', async () => {
    const prompt = document.getElementById('prompt-input').value;
    if (!prompt) return;

    const btn = document.getElementById('generate-btn');
    const overlay = document.getElementById('full-page-overlay');
    const overlaySpinner = document.getElementById('overlay-spinner');
    const overlayMessage = document.getElementById('overlay-message');
    const overlayError = document.getElementById('overlay-error');
    const overlayClose = document.getElementById('overlay-close');
    const resultsSection = document.getElementById('results-section');

    // Reset overlay state
    overlaySpinner.classList.remove('hidden');
    overlayMessage.innerText = 'Orchestrating your trip...';
    overlayError.classList.add('hidden');
    overlayClose.classList.add('hidden');

    btn.disabled = true;
    overlay.classList.remove('hidden');
    resultsSection.classList.add('hidden');

    let success = false;
    startProgress();

    try {
        const response = await fetch('/api/plan-trip', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ prompt })
        });

        const data = await response.json();

        if (response.ok) {
            renderBudgetAnalysis(data.budget_recommendation);
            if (data.flights) renderFlights(data.flights, data.currency);
            renderItinerary(data.itinerary, data.currency);
            renderLedger(data.split);
            resultsSection.classList.remove('hidden');
            resultsSection.scrollIntoView({ behavior: 'smooth' });
            success = true;
        } else {
            stopProgress(false);
            showErrorInOverlay(data.detail || 'Failed to generate itinerary.');
        }
    } catch (error) {
        console.error('Frontend Error:', error);
        stopProgress(false);
        showErrorInOverlay('Frontend Error: ' + error.message);
    } finally {
        btn.disabled = false;
        if (success) {
            stopProgress(true);
            setTimeout(() => {
                overlay.classList.add('hidden');
            }, 500); // Wait a half second so user sees 100% completion
        }
    }
});

let progressInterval;

function startProgress() {
    const bar = document.getElementById('progress-bar');
    const statusText = document.getElementById('overlay-status-text');
    let progress = 0;
    
    const statuses = [
        { threshold: 0, text: 'Analyzing destination context...' },
        { threshold: 15, text: 'Querying live flight prices...' },
        { threshold: 35, text: 'Sourcing realistic hotel rates...' },
        { threshold: 55, text: 'Drafting day-by-day itinerary...' },
        { threshold: 75, text: 'Finalizing budget split...' },
        { threshold: 95, text: 'Applying Apple-style polish...' }
    ];

    bar.style.width = '0%';
    document.getElementById('progress-container').classList.remove('hidden');
    statusText.classList.remove('hidden');
    statusText.innerText = statuses[0].text;

    progressInterval = setInterval(() => {
        if (progress < 95) {
            const increment = Math.max(0.2, (95 - progress) / 20);
            progress += increment;
            bar.style.width = `${progress}%`;
            
            const currentStatus = statuses.slice().reverse().find(s => progress >= s.threshold);
            if (currentStatus) {
                statusText.innerText = currentStatus.text;
            }
        }
    }, 400);
}

function stopProgress(success) {
    clearInterval(progressInterval);
    const bar = document.getElementById('progress-bar');
    const statusText = document.getElementById('overlay-status-text');
    if (success) {
        bar.style.width = '100%';
        statusText.innerText = 'Complete!';
    } else {
        document.getElementById('progress-container').classList.add('hidden');
        statusText.classList.add('hidden');
    }
}

function showErrorInOverlay(errorMessage) {
    const overlaySpinner = document.getElementById('overlay-spinner');
    const overlayMessage = document.getElementById('overlay-message');
    const overlayError = document.getElementById('overlay-error');
    const overlayClose = document.getElementById('overlay-close');

    overlaySpinner.classList.add('hidden');
    overlayMessage.innerText = 'Error';
    overlayError.innerText = errorMessage;
    overlayError.classList.remove('hidden');
    overlayClose.classList.remove('hidden');
}

document.getElementById('overlay-close').addEventListener('click', () => {
    document.getElementById('full-page-overlay').classList.add('hidden');
});

function renderBudgetAnalysis(recommendation) {
    const banner = document.getElementById('budget-banner');
    const status = document.getElementById('budget-status');
    const message = document.getElementById('budget-message');
    
    if (!recommendation) {
        banner.classList.add('hidden');
        return;
    }
    
    banner.classList.remove('hidden');
    banner.classList.remove('success', 'warning');
    
    if (recommendation.is_sufficient) {
        banner.classList.add('success');
        status.innerText = 'Budget Looks Good';
    } else {
        banner.classList.add('warning');
        status.innerText = 'Budget Alert';
    }
    message.innerText = recommendation.message;
}

function renderFlights(flights, currency) {
    const section = document.querySelector('.flights-section');
    if (!flights) {
        section.classList.add('hidden');
        return;
    }
    
    section.classList.remove('hidden');
    document.getElementById('flight-cost').innerText = `${flights.cost} ${currency}`;
    const sourceLink = document.getElementById('flight-source');
    sourceLink.href = flights.source.startsWith('http') ? flights.source : `https://${flights.source}`;
    sourceLink.innerText = 'View Source ↗';
}

function renderItinerary(itinerary, currency) {
    const container = document.getElementById('itinerary-content');
    container.innerHTML = '';

    itinerary.forEach(day => {
        const card = document.createElement('div');
        card.className = 'day-card';
        
        const activitiesHtml = day.activities.map(act => {
            const sourceHref = act.source.startsWith('http') ? act.source : `https://${act.source}`;
            return `
            <li>
                <span class="activity-name">${act.name}</span>
                <div class="activity-meta">
                    <span class="cost-tag">${act.cost} ${currency}</span>
                    <a href="${sourceHref}" target="_blank" class="source-link">Source ↗</a>
                </div>
            </li>
            `;
        }).join('');

        card.innerHTML = `
            <h4>Day ${day.day}: ${day.location}</h4>
            <ul>
                ${activitiesHtml}
            </ul>
            <div class="daily-summary">
                <span>Hotel: ${day.daily_hotel_cost} ${currency}</span>
                <span>Food: ${day.daily_food_cost} ${currency}</span>
                <span>Transport: ${day.daily_transport_cost} ${currency}</span>
            </div>
        `;
        container.appendChild(card);
    });
}

function renderLedger(split) {
    document.getElementById('total-cost').innerText = `${split.total} ${split.currency}`;
    document.getElementById('split-person').innerText = `${split.split_per_person} ${split.currency}`;
    document.getElementById('split-local').innerText = `${split.split_per_person_local} ${split.local_currency}`;
}

document.getElementById('settle-btn').addEventListener('click', async () => {
    const cardInput = document.getElementById('card-input').value;
    const msgEl = document.getElementById('settle-message');

    if (!cardInput) return;

    try {
        const response = await fetch('/api/settle', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                group_id: "group_123",
                user_id: "user_1",
                card_number: cardInput
            })
        });

        const data = await response.json();

        if (response.ok) {
            msgEl.innerText = data.message;
            msgEl.style.color = "var(--success)";
        } else {
            msgEl.innerText = data.detail;
            msgEl.style.color = "var(--error)";
        }
    } catch (error) {
        msgEl.innerText = "Connection failed.";
        msgEl.style.color = "var(--error)";
    }
});
