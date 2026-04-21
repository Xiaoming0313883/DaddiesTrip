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
        const response = await fetch('/api/plan-trip-stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt })
        });

        if (!response.ok) {
            const errData = await response.json();
            stopProgress(false);
            showErrorInOverlay(errData.detail || 'Failed to connect.');
            btn.disabled = false;
            return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            let lines = buffer.split('\n\n');
            buffer = lines.pop(); // keep last incomplete part

            for (let line of lines) {
                if (line.startsWith('data: ')) {
                    const dataStr = line.substring(6);
                    try {
                        const event = JSON.parse(dataStr);
                        if (event.type === 'progress') {
                            updateProgressStatus(event.text);
                        } else if (event.type === 'error') {
                            stopProgress(false);
                            showErrorInOverlay(event.message);
                            btn.disabled = false;
                            return; // exit loop
                        } else if (event.type === 'complete') {
                            const data = event.data;
                            renderBudgetAnalysis(data.budget_recommendation);
                            if (data.flight_options && data.flight_options.length > 0) {
                                renderFlightOptions(data.flight_options);
                            } else if (data.flights) {
                                renderFlightOptions([data.flights]);
                            }
                            renderItinerary(data.itinerary);
                            renderLedger(data.split, data.itinerary, data.flights || (data.flight_options && data.flight_options[0]));
                            resultsSection.classList.remove('hidden');
                            if (document.getElementById('pdf-action-container')) {
                                document.getElementById('pdf-action-container').classList.remove('hidden');
                            }
                            resultsSection.scrollIntoView({ behavior: 'smooth' });
                            success = true;
                        }
                    } catch (e) { console.error('Parse error', e); }
                }
            }
        }
    } catch (error) {
        console.error('Frontend Error:', error);
        stopProgress(false);
        showErrorInOverlay('Frontend Error: ' + error.message);
    } finally {
        btn.disabled = false;
        if (success) {
            stopProgress(true);
            setTimeout(() => { overlay.classList.add('hidden'); }, 500);
        }
    }
});

let currentProgress = 0;

function startProgress() {
    const container = document.getElementById('progress-container');
    const bar = document.getElementById('progress-bar');
    const statusText = document.getElementById('overlay-status-text');
    currentProgress = 0;

    bar.style.width = '0%';
    container.classList.remove('hidden');
    statusText.classList.remove('hidden');
    statusText.innerText = "Initializing orchestrator...";
}

function updateProgressStatus(text) {
    const statusText = document.getElementById('overlay-status-text');
    const bar = document.getElementById('progress-bar');
    statusText.innerText = text;
    currentProgress += 15;
    if (currentProgress > 95) currentProgress = 95;
    bar.style.width = `${currentProgress}%`;
}

function stopProgress(success) {
    const bar = document.getElementById('progress-bar');
    const statusText = document.getElementById('overlay-status-text');
    if (success) {
        bar.style.width = '100%';
        statusText.innerText = 'Done!';
    }
}

function showErrorInOverlay(errorMessage) {
    const overlaySpinner = document.getElementById('overlay-spinner');
    const overlayMessage = document.getElementById('overlay-message');
    const overlayError = document.getElementById('overlay-error');
    const overlayClose = document.getElementById('overlay-close');

    // Keep detailed errors in the console
    console.error('Backend Detail:', errorMessage);

    overlaySpinner.classList.add('hidden');
    overlayMessage.innerText = 'Error';
    overlayError.innerText = 'An error occurred during orchestration. Please contact the admin.';
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

    if (!recommendation) { banner.classList.add('hidden'); return; }

    banner.classList.remove('hidden', 'success', 'warning');

    if (recommendation.is_sufficient) {
        banner.classList.add('success');
        status.innerText = 'Budget Looks Good';
    } else {
        banner.classList.add('warning');
        status.innerText = 'Budget Alert';
    }
    message.innerText = recommendation.message;
}

let selectedFlightOption = null;

function renderFlightOptions(options) {
    const section = document.querySelector('.flights-section');
    const list = document.getElementById('flight-options-list');
    const costEl = document.getElementById('flight-cost');
    const sourceEl = document.getElementById('flight-source');
    const subtitle = document.querySelector('.flights-subtitle');

    if (!options || options.length === 0) {
        section.classList.remove('hidden');
        list.innerHTML = '<div style="padding: 1rem; background: var(--bg-card); border-radius: 8px;"><strong>🚗 Local Trip:</strong> Flights are not required for this itinerary route. Enjoy your drive/transit!</div>';
        costEl.innerText = `RM 0`;
        sourceEl.classList.add('hidden');
        if (subtitle) subtitle.classList.add('hidden');
        selectedFlightOption = { cost_myr: 0 };
        return;
    }

    section.classList.remove('hidden');
    sourceEl.classList.remove('hidden');
    if (subtitle) subtitle.classList.remove('hidden');
    list.innerHTML = '';

    options.forEach((opt, i) => {
        const dep = opt.departure || {};
        const ret = opt.return || {};
        const airline = opt.airline || `Option ${i + 1}`;
        const iata = opt.airline_iata || "MH";
        const iconUrl = `https://pics.avs.io/60/60/${iata}.png`;
        const cost = opt.cost_myr || 0;
        const depStr = `KUL ${dep.time || ''} ${dep.date || ''}`;
        const retStr = `${ret.airport || '?'} → KUL ${ret.time || ''}`;

        const row = document.createElement('label');
        row.className = 'flight-option-row' + (i === 0 ? ' selected' : '');
        row.innerHTML = `
            <input type="radio" name="flight_pick" value="${i}" ${i === 0 ? 'checked' : ''}>
            <div class="flight-option-info">
                <img src="${iconUrl}" alt="${airline} logo" width="30" height="30" style="border-radius: 4px; object-fit: cover; margin-right: 10px;" onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22><path d=%22M21 16v-2l-8-5V3.5c0-.83-.67-1.5-1.5-1.5S10 2.67 10 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5l8 2.5z%22/></svg>';" />
                <span class="flight-airline">${airline}</span>
                <span class="flight-route">${depStr} → ${retStr}</span>
            </div>
            <span class="flight-option-price">RM ${cost}</span>
        `;
        row.querySelector('input').addEventListener('change', () => {
            document.querySelectorAll('.flight-option-row').forEach(r => r.classList.remove('selected'));
            row.classList.add('selected');
            selectedFlightOption = opt;
            costEl.innerText = `RM ${cost}`;
            const src = opt.source || '#';
            sourceEl.href = src.startsWith('http') ? src : `https://${src}`;
        });
        list.appendChild(row);
    });

    selectedFlightOption = options[0];
    costEl.innerText = `RM ${options[0].cost_myr || 0}`;
    const src0 = options[0].source || '#';
    sourceEl.href = src0.startsWith('http') ? src0 : `https://${src0}`;
}

function renderItinerary(itinerary) {
    const container = document.getElementById('itinerary-content');
    container.innerHTML = '';

    itinerary.forEach(day => {
        const card = document.createElement('div');
        card.className = 'day-card';

        const activitiesHtml = day.activities ? day.activities.map(act => {
            const nameLC = (act.name || '').toLowerCase();
            const isTicketed = nameLC.includes('ticket required');
            const isFree = nameLC.includes('free');
            const badgeHtml = isTicketed
                ? `<span class="ticket-badge required">🎟 Ticket Required</span>`
                : isFree ? `<span class="ticket-badge free">✓ Free Entry</span>` : '';

            const embedMap = `https://maps.google.com/maps?q=${encodeURIComponent(act.name + ' ' + day.location)}&t=&z=14&ie=UTF8&iwloc=&output=embed`;

            return `
            <li>
                <div class="activity-header">
                    <span class="activity-name">${act.name}</span>
                    <div style="font-size: 0.85em; color: var(--text-secondary); margin-top: 4px;">🗓 ${act.schedule || 'Scheduled Time'}</div>
                    ${badgeHtml}
                </div>
                <div class="activity-meta" style="margin-bottom: 10px;">
                    <span class="cost-tag">RM ${act.cost_myr || 0}</span>
                </div>
                <div class="map-embed-container" style="border-radius: 8px; overflow: hidden; margin-top: 10px; border: 1px solid rgba(255,255,255,0.1);">
                    <iframe src="${embedMap}" width="100%" height="150" style="border:0;" allowfullscreen="" loading="lazy"></iframe>
                </div>
            </li>`;
        }).join('') : '';

        const hotelName = day.hotel ? day.hotel.name : 'Not Specified';
        const hotelCost = day.hotel ? day.hotel.cost_myr : 0;
        const foodRecs = day.food_recommendations ? day.food_recommendations.join(', ') : 'No recommendations';
        const foodCost = day.daily_food_cost_myr || 0;
        const transRoute = day.transportation ? day.transportation.route : 'Local transit';
        const transCost = day.transportation ? day.transportation.cost_myr : 0;

        card.innerHTML = `
            <h4>Day ${day.day}: ${day.location}</h4>
            <ul>${activitiesHtml}</ul>
            <div class="daily-modules">
                <div class="module-box">
                    <h5>🏨 Stay</h5>
                    <p>${hotelName}</p>
                    <span class="cost-tag">RM ${hotelCost} / night</span>
                </div>
                <div class="module-box">
                    <h5>🍜 Eat</h5>
                    <p>${foodRecs}</p>
                    <span class="cost-tag">RM ${foodCost} / day</span>
                </div>
                <div class="module-box">
                    <h5>🚇 Transit</h5>
                    <p>${transRoute}</p>
                    <span class="cost-tag">RM ${transCost} / day</span>
                </div>
            </div>
        `;
        container.appendChild(card);
    });
}

let currentTripData = null;

function renderLedger(split, itinerary, flights) {
    if (!split || !split.primary_currency) return;
    currentTripData = { split, itinerary, flights };
    document.getElementById('total-cost').innerText = `RM ${split.total_myr}`;
    document.getElementById('split-person').innerText = `RM ${split.split_per_person_myr}`;
    document.getElementById('local-currency-label').innerText = `Local (${split.destination_currency})`;
    document.getElementById('split-local').innerText = `${split.split_per_person_local} ${split.destination_currency}`;
}

document.getElementById('review-budget-btn').addEventListener('click', () => {
    if (!currentTripData) return;
    populateAccountingTable(currentTripData);
    document.getElementById('budget-modal').classList.remove('hidden');
});

document.getElementById('close-budget-btn').addEventListener('click', () => {
    document.getElementById('budget-modal').classList.add('hidden');
});

function populateAccountingTable(data) {
    const { split, itinerary, flights } = data;
    let hotelTotal = 0, foodTotal = 0, transTotal = 0, actTotal = 0;

    itinerary.forEach(day => {
        hotelTotal += (day.hotel ? day.hotel.cost_myr : 0);
        foodTotal += (day.daily_food_cost_myr || 0);
        transTotal += (day.transportation ? day.transportation.cost_myr : 0);
        if (day.activities) day.activities.forEach(act => actTotal += (act.cost_myr || 0));
    });

    const flightCost = selectedFlightOption ? (selectedFlightOption.cost_myr || 0) : (flights ? (flights.cost_myr || 0) : 0);

    document.getElementById('acc-flights').innerText = `RM ${flightCost}`;
    document.getElementById('acc-hotel').innerText = `RM ${hotelTotal}`;
    document.getElementById('acc-food').innerText = `RM ${foodTotal}`;
    document.getElementById('acc-trans').innerText = `RM ${transTotal}`;
    document.getElementById('acc-act').innerText = `RM ${actTotal}`;
    document.getElementById('acc-total').innerText = `RM ${split.total_myr}`;
}

// Live card preview
document.getElementById('card-input').addEventListener('input', (e) => {
    let val = e.target.value.replace(/\D/g, '').substring(0, 16);
    let formatted = val.match(/.{1,4}/g)?.join(' ') || val;
    e.target.value = formatted;
    document.getElementById('card-number-display').innerText = formatted || '•••• •••• •••• ••••';
});

document.getElementById('card-holder').addEventListener('input', (e) => {
    document.getElementById('card-holder-display').innerText = e.target.value.toUpperCase() || 'YOUR NAME';
});

document.getElementById('card-expiry').addEventListener('input', (e) => {
    let val = e.target.value.replace(/\D/g, '').substring(0, 4);
    if (val.length >= 3) val = val.substring(0, 2) + '/' + val.substring(2);
    e.target.value = val;
    document.getElementById('card-expiry-display').innerText = val || 'MM/YY';
});

// Payment Sequence
document.getElementById('settle-btn').addEventListener('click', async () => {
    const cardInput = document.getElementById('card-input').value.replace(/\s/g, '');
    const msgEl = document.getElementById('settle-message');

    if (cardInput.length < 16) {
        msgEl.innerText = 'Please enter a valid 16-digit card number.';
        msgEl.style.color = 'var(--error)';
        return;
    }

    document.getElementById('budget-modal').classList.add('hidden');
    const paymentModal = document.getElementById('payment-modal');
    const statusText = document.getElementById('payment-status-text');

    paymentModal.classList.remove('hidden');
    statusText.innerText = 'Processing...';

    setTimeout(async () => {
        try {
            const response = await fetch('/api/settle', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ group_id: "group_123", user_id: "user_1", card_number: cardInput })
            });
            const data = await response.json();

            if (response.ok) {
                statusText.innerText = 'Payment Successful!';
                setTimeout(() => paymentModal.classList.add('hidden'), 3000);
            } else {
                paymentModal.classList.add('hidden');
                msgEl.innerText = data.detail;
                msgEl.style.color = 'var(--error)';
                document.getElementById('budget-modal').classList.remove('hidden');
            }
        } catch (error) {
            paymentModal.classList.add('hidden');
            msgEl.innerText = 'Connection failed.';
            msgEl.style.color = 'var(--error)';
            document.getElementById('budget-modal').classList.remove('hidden');
        }
    }, 2000);
});

// PDF Generation
document.getElementById('download-pdf-btn').addEventListener('click', () => {
    const element = document.getElementById('results-section');
    const opt = {
        margin: 0.5,
        filename: 'DaddiesTrip_Itinerary.pdf',
        image: { type: 'jpeg', quality: 0.98 },
        html2canvas: { scale: 2 },
        jsPDF: { unit: 'in', format: 'letter', orientation: 'portrait' }
    };
    // Hide buttons temporarily
    document.getElementById('pdf-action-container').classList.add('hidden');
    document.querySelector('.settlement-ui').classList.add('hidden');

    html2pdf().set(opt).from(element).save().then(() => {
        document.getElementById('pdf-action-container').classList.remove('hidden');
        document.querySelector('.settlement-ui').classList.remove('hidden');
    });
});
