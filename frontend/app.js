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

    // Dismiss any existing clarification banner when starting a new generation
    const existingClarif = document.getElementById('clarification-banner');
    if (existingClarif) existingClarif.remove();

    overlaySpinner.classList.remove('hidden');
    overlayMessage.innerText = 'Orchestrating your trip...';
    overlayError.classList.add('hidden');
    overlayClose.classList.add('hidden');

    btn.disabled = true;
    overlay.classList.remove('hidden');
    resultsSection.classList.add('hidden');

    // Clear any previous error banner
    const existingBanner = document.getElementById('error-banner');
    if (existingBanner) existingBanner.remove();

    let success = false;
    let startTime = Date.now();
    startProgress();

    try {
        const response = await fetch('/api/plan-trip-stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt })
        });

        if (!response.ok) {
            let errDetail = `HTTP ${response.status}`;
            if (response.status === 504 || response.status === 502) {
                errDetail = 'The AI service is temporarily unavailable (gateway timeout). Please wait a moment and try again.';
            } else if (response.status === 429) {
                errDetail = 'Too many requests. Please wait a moment and try again.';
            } else if (response.status >= 500) {
                errDetail = `Server error (HTTP ${response.status}). Please try again later.`;
            } else {
                try { const errData = await response.json(); errDetail = errData.detail || errDetail; } catch (_) {}
            }
            stopProgress(false);
            showErrorInOverlay(errDetail);
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
            buffer = lines.pop();

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
                            return;
                        } else if (event.type === 'clarification') {
                            stopProgress(false);
                            overlay.classList.add('hidden');
                            showClarificationBanner(
                                event.message,
                                event.missing_fields || []
                            );
                            btn.disabled = false;
                            return;
                        } else if (event.type === 'partial_itinerary') {
                            renderPartialItinerary(event.days, event.num_participants);
                            resultsSection.classList.remove('hidden');
                        } else if (event.type === 'partial_flights') {
                            renderFlightOptions(event.flight_options, event.num_participants);
                        } else if (event.type === 'complete') {
                            const data = event.data;
                            const numPax = data.num_participants || data.participants?.length || 1;

                            renderBudgetAnalysis(data.budget_recommendation);
                            if (data.flight_options && data.flight_options.length > 0) {
                                renderFlightOptions(data.flight_options, numPax);
                            } else if (data.flights) {
                                renderFlightOptions([data.flights], numPax);
                            }
                            renderItinerary(data.itinerary, data.destination_review, numPax);
                            renderLedger(data.split, data.itinerary, data.flights || (data.flight_options && data.flight_options[0]), numPax);
                            resultsSection.classList.remove('hidden');

                            let timeTaken = ((Date.now() - startTime) / 1000).toFixed(1);
                            let timeEl = document.getElementById('response-time');
                            if (!timeEl) {
                                timeEl = document.createElement('div');
                                timeEl.id = 'response-time';
                                timeEl.className = 'response-time-badge';
                                resultsSection.insertBefore(timeEl, resultsSection.firstChild);
                            }
                            timeEl.innerText = `Completed in ${timeTaken}s`;

                            resultsSection.scrollIntoView({ behavior: 'smooth' });
                            success = true;
                        }
                    } catch (e) { console.error('Parse error:', dataStr, e); }
                }
            }
        }
        if (!success && document.getElementById('overlay-error').classList.contains('hidden')) {
            stopProgress(false);
            showErrorInOverlay('Server stopped responding. Try a simpler prompt.');
        }
    } catch (error) {
        stopProgress(false);
        const msg = error.name === 'TypeError' && error.message.includes('Failed to fetch')
            ? 'Unable to connect to the server. Please check your internet connection and try again.'
            : 'Connection error: ' + error.message;
        showErrorInOverlay(msg);
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
    document.getElementById('overlay-status-text').innerText = text;
    currentProgress += 15;
    if (currentProgress > 95) currentProgress = 95;
    document.getElementById('progress-bar').style.width = `${currentProgress}%`;
}
function stopProgress(success) {
    if (success) {
        document.getElementById('progress-bar').style.width = '100%';
        document.getElementById('overlay-status-text').innerText = 'Done!';
    }
}
function showErrorInOverlay(msg) {
    document.getElementById('overlay-spinner').classList.add('hidden');
    document.getElementById('overlay-message').innerText = 'Something went wrong';
    const el = document.getElementById('overlay-error');
    el.style.color = '';
    el.innerText = msg || 'An error occurred. Please try again.';
    el.classList.remove('hidden');
    document.getElementById('overlay-close').classList.remove('hidden');
    // Also show a banner on the main page
    showErrorBanner(msg);
}
function showClarificationBanner(msg, missingFields) {
    // Remove any existing clarification banner
    const existing = document.getElementById('clarification-banner');
    if (existing) existing.remove();

    const PILL_MAP = {
        destination:  { icon: '📍', label: 'Destination' },
        trip_dates:   { icon: '🗓️', label: 'Trip Dates' },
        participants: { icon: '👥', label: 'Participants' },
        budget:       { icon: '💰', label: 'Budget' },
    };

    const pillsHtml = (missingFields || []).map(f => {
        const p = PILL_MAP[f] || { icon: '❓', label: f };
        return `<span class="missing-pill">${p.icon} ${p.label}</span>`;
    }).join('');

    const banner = document.createElement('div');
    banner.id = 'clarification-banner';
    banner.className = 'clarification-banner';
    banner.innerHTML = `
        <div class="clarif-header">
            <span class="clarif-title">📋 Missing Information</span>
            <button class="clarif-close" onclick="this.closest('#clarification-banner').remove()">✕</button>
        </div>
        ${pillsHtml ? `<div class="clarif-pills">${pillsHtml}</div>` : ''}
        <p class="clarif-message">${msg || 'Please add the missing details to your request.'}</p>
    `;

    const inputSection = document.querySelector('.input-section');
    inputSection.insertAdjacentElement('afterend', banner);
    banner.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function showClarificationInOverlay(msg) {
    document.getElementById('overlay-spinner').classList.add('hidden');
    document.getElementById('overlay-message').innerText = 'Tell me more';
    const el = document.getElementById('overlay-error');
    el.style.color = 'var(--text-primary)';
    el.innerText = msg;
    el.classList.remove('hidden');
    document.getElementById('overlay-close').classList.remove('hidden');
}
document.getElementById('overlay-close').addEventListener('click', () => {
    document.getElementById('full-page-overlay').classList.add('hidden');
});

function showErrorBanner(msg) {
    // Remove any existing banner
    const existing = document.getElementById('error-banner');
    if (existing) existing.remove();

    const banner = document.createElement('div');
    banner.id = 'error-banner';
    banner.className = 'error-banner';
    banner.innerHTML = `
        <div class="error-banner-icon">⚠️</div>
        <div class="error-banner-text">${msg || 'An error occurred. Please try again.'}</div>
        <button class="error-banner-close" onclick="this.parentElement.remove()">✕</button>
    `;
    const mainContent = document.querySelector('.main-content');
    mainContent.insertBefore(banner, mainContent.firstChild);
    banner.scrollIntoView({ behavior: 'smooth' });
}

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
let numParticipants = 1;

function renderFlightOptions(options, numPax) {
    numParticipants = numPax;
    const section = document.querySelector('.flights-section');
    const list = document.getElementById('flight-options-list');
    const costEl = document.getElementById('flight-cost');
    const sourceEl = document.getElementById('flight-source');
    const subtitle = document.querySelector('.flights-subtitle');

    if (!options || options.length === 0) {
        section.classList.remove('hidden');
        list.innerHTML = '<div style="padding:0.75rem; border-radius:8px;"><strong>Local Trip:</strong> No flights needed.</div>';
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
        const iconUrl = `https://pics.avs.io/50/50/${iata}.png`;
        const costPerPax = opt.cost_myr || 0;
        const costTotal = costPerPax * numPax;

        // Build date-specific Skyscanner link
        let skyscannerHref = opt.source || '#';
        if (skyscannerHref === '#' || !skyscannerHref.includes('/kul/')) {
            const destIATA = (ret.airport || '').toLowerCase() || 'sin';
            const depD = (dep.date || '').replace(/-/g, '');
            const retD = (ret.date || '').replace(/-/g, '');
            if (depD.length >= 8 && retD.length >= 8) {
                skyscannerHref = `https://www.skyscanner.com.my/transport/flights/kul/${destIATA}/${depD.slice(2)}/${retD.slice(2)}/`;
            }
        }

        // Build Google Flights link with specific date + locale params for reliable deep-link
        let googleFlightsHref = opt.google_flights || '#';
        if (googleFlightsHref === '#' || !googleFlightsHref.includes('on+')) {
            const destIATA = ret.airport || 'SIN';
            const airlineName = (opt.airline || '').replace(/\s+/g, '+');
            const depDateStr = dep.date || '';
            if (depDateStr) {
                googleFlightsHref = `https://www.google.com/travel/flights?q=Flights+from+KUL+to+${destIATA}+on+${depDateStr}${airlineName ? '+with+' + airlineName : ''}&curr=MYR&hl=en&gl=MY`;
            }
        } else if (!googleFlightsHref.includes('hl=en')) {
            googleFlightsHref += '&hl=en&gl=MY';
        }

        const row = document.createElement('label');
        row.className = 'flight-option-row' + (i === 0 ? ' selected' : '');
        row.innerHTML = `
            <input type="radio" name="flight_pick" value="${i}" ${i === 0 ? 'checked' : ''}>
            <div class="flight-option-info">
                <div style="display:flex; align-items:center; gap:8px;">
                    <img src="${iconUrl}" alt="${airline}" width="24" height="24" style="border-radius:4px;" onerror="this.style.display='none';" />
                    <span class="flight-airline">${airline}</span>
                </div>
                <div class="flight-legs">
                    <div class="flight-leg">
                        <span class="flight-leg-label">Depart</span>
                        <span class="flight-leg-route">${dep.airport || 'KUL'} → ${ret.airport || '?'}</span>
                        <span class="flight-leg-detail">${dep.date || ''} ${dep.time || ''} ${dep.arrival_time ? '– ' + dep.arrival_time : ''}</span>
                    </div>
                    <div class="flight-leg">
                        <span class="flight-leg-label">Return</span>
                        <span class="flight-leg-route">${ret.airport || '?'} → KUL</span>
                        <span class="flight-leg-detail">${ret.date || ''} ${ret.time || ''} ${ret.arrival_time ? '– ' + ret.arrival_time : ''}</span>
                    </div>
                </div>
                <div class="flight-pricing">
                    <span class="flight-price-pax">RM ${costPerPax}/pax</span>
                    <span class="flight-price-total">Total RM ${costTotal} (${numPax} pax)</span>
                </div>
                <div style="display:flex; gap:0.4rem; flex-wrap:wrap; margin-top:0.25rem;">
                    <a href="${skyscannerHref}" target="_blank" rel="noopener" class="flight-detail-link">Skyscanner ↗</a>
                    <a href="${googleFlightsHref}" target="_blank" rel="noopener" class="flight-detail-link">Google Flights ↗</a>
                </div>
            </div>
        `;
        row.querySelector('input').addEventListener('change', () => {
            document.querySelectorAll('.flight-option-row').forEach(r => r.classList.remove('selected'));
            row.classList.add('selected');
            selectedFlightOption = opt;
            costEl.innerText = `RM ${costTotal}`;
            sourceEl.href = googleFlightsHref.startsWith('http') ? googleFlightsHref : `https://${googleFlightsHref}`;
            sourceEl.innerText = `Search ${airline} on Google Flights ↗`;
        });
        list.appendChild(row);
    });

    // Disclaimer
    const disclaimer = document.createElement('div');
    disclaimer.className = 'flight-disclaimer';
    disclaimer.innerText = 'Prices are estimates per person. Click links to verify live fares and times.';
    list.appendChild(disclaimer);

    selectedFlightOption = options[0];
    costEl.innerText = `RM ${(options[0].cost_myr || 0) * numPax}`;
    let gf0 = options[0].google_flights || '#';
    if (gf0 === '#' || !gf0.includes('on+')) {
        const destIATA = (options[0].return || {}).airport || 'SIN';
        const airlineName0 = (options[0].airline || '').replace(/\s+/g, '+');
        const depDateStr = (options[0].departure || {}).date || '';
        if (depDateStr) gf0 = `https://www.google.com/travel/flights?q=Flights+from+KUL+to+${destIATA}+on+${depDateStr}${airlineName0 ? '+with+' + airlineName0 : ''}&curr=MYR&hl=en&gl=MY`;
    } else if (!gf0.includes('hl=en')) {
        gf0 += '&hl=en&gl=MY';
    }
    sourceEl.href = gf0.startsWith('http') ? gf0 : `https://${gf0}`;
    sourceEl.innerText = `Search ${options[0].airline || 'Flights'} on Google Flights ↗`;
}

function renderStars(rating) {
    if (!rating) return '';
    const num = parseFloat(rating);
    if (isNaN(num)) return `<span class="dest-stars">${rating}</span>`;
    let stars = '';
    for (let s = 0; s < Math.floor(num); s++) stars += '★';
    if ((num - Math.floor(num)) >= 0.3) stars += '½';
    return `<span class="dest-stars">${stars}</span>`;
}

function renderPartialItinerary(days, numPax) {
    const container = document.getElementById('itinerary-content');
    if (!container) return;
    container.innerHTML = '';
    
    if (days && days.length > 0) {
        const destName = days[0].location || 'Destination';
        const reviewCard = document.createElement('div');
        reviewCard.className = 'destination-review';
        reviewCard.innerHTML = `<div class="dest-info"><div class="dest-name">${destName}</div></div>`;
        container.appendChild(reviewCard);
    }

    days.forEach((day, dayIdx) => {
        const card = document.createElement('div');
        card.className = 'day-card';
        const dayNum = day.day || (dayIdx + 1);
        const dayLocation = day.location || 'Destination';

        let activitiesHtml = '';
        if (day.activities && day.activities.length > 0) {
            day.activities.forEach(act => {
                activitiesHtml += `
                <li>
                    <div class="activity-header">
                        <span class="activity-name">${act.name || 'Activity'}</span>
                        <div style="font-size:0.8em; color:var(--text-secondary);">${act.schedule || ''}</div>
                    </div>
                </li>`;
            });
        } else {
            activitiesHtml = '<li><div class="skeleton-line medium"></div></li>';
        }

        card.innerHTML = `
            <h4>Day ${dayNum}: ${dayLocation}</h4>
            <ul>${activitiesHtml}</ul>
            <div class="daily-modules">
                <div class="module-box">
                    <h5>Stay</h5>
                    <div class="skeleton-line full"></div>
                    <div class="skeleton-line short"></div>
                    <span class="partial-loading-tag">⏳ Loading cost...</span>
                </div>
                <div class="module-box">
                    <h5>Eat</h5>
                    <div class="skeleton-line medium"></div>
                    <span class="partial-loading-tag">⏳ Loading cost...</span>
                </div>
                <div class="module-box">
                    <h5>Transit</h5>
                    <div class="skeleton-line short"></div>
                    <span class="partial-loading-tag">⏳ Loading cost...</span>
                </div>
            </div>
        `;
        container.appendChild(card);
    });
}

function renderItinerary(itinerary, destinationReview, numPax) {
    numParticipants = numPax;
    const container = document.getElementById('itinerary-content');
    container.innerHTML = '';

    // Destination review
    if (destinationReview) {
        const reviewCard = document.createElement('div');
        reviewCard.className = 'destination-review';
        const destName = destinationReview.name || itinerary[0]?.location || 'Destination';
        const mapLink = `https://www.google.com/maps/search/${encodeURIComponent(destName)}`;
        reviewCard.innerHTML = `
            <div class="dest-info">
                <div class="dest-name">${destName}</div>
                <div class="dest-rating">
                    ${renderStars(destinationReview.rating)}
                    <span class="dest-score">${destinationReview.rating || ''}</span>
                    ${destinationReview.review_count ? `<span class="dest-review-count">(${destinationReview.review_count} reviews)</span>` : ''}
                </div>
                ${destinationReview.review_comment ? `<div class="dest-comment">"${destinationReview.review_comment}"</div>` : ''}
                <a href="${mapLink}" target="_blank" rel="noopener" class="dest-map-link">View on Google Maps ↗</a>
            </div>
        `;
        container.appendChild(reviewCard);
    } else if (itinerary && itinerary.length > 0) {
        const destName = itinerary[0]?.location || 'Destination';
        const mapLink = `https://www.google.com/maps/search/${encodeURIComponent(destName)}`;
        const reviewCard = document.createElement('div');
        reviewCard.className = 'destination-review';
        reviewCard.innerHTML = `<div class="dest-info"><div class="dest-name">${destName}</div><a href="${mapLink}" target="_blank" rel="noopener" class="dest-map-link">View on Google Maps ↗</a></div>`;
        container.appendChild(reviewCard);
    }

    itinerary.forEach((day, dayIdx) => {
        const card = document.createElement('div');
        card.className = 'day-card';

        // Defensive: ensure day number and location always have values
        const dayNum = day.day || (dayIdx + 1);
        const dayLocation = day.location || 'Destination';
        const dayActivities = Array.isArray(day.activities) ? day.activities : [];

        // Mode icons for transport connectors
        const modeIcon = { walk: '🚶', bus: '🚌', metro: '🚇', taxi: '🚕', ferry: '⛴️', tram: '🚊' };

        // Build activity list items + transport connectors
        let activitiesHtml = '';
        if (dayActivities.length === 0) {
            activitiesHtml = '<li style="color:var(--text-secondary); font-style:italic;">No activities listed for this day.</li>';
        } else {
            dayActivities.forEach((act, actIdx) => {
                const nameLC = (act.name || '').toLowerCase();
                const isTicketed = nameLC.includes('ticket required');
                const isFree = nameLC.includes('free');
                const badgeHtml = isTicketed
                    ? `<span class="ticket-badge required">Ticket</span>`
                    : isFree ? `<span class="ticket-badge free">Free</span>` : '';

                const embedMap = `https://maps.google.com/maps?q=${encodeURIComponent((act.name || 'location') + ' ' + dayLocation)}&t=&z=14&ie=UTF8&iwloc=&output=embed`;
                const actCostPax = act.cost_myr || 0;
                const actCostTotal = actCostPax * numPax;

                const ratingHtml = act.rating ? `<span style="color:#f5b041; font-weight:bold;">★ ${act.rating}</span>` : '';
                const reviewHtml = act.review_comment ? `<span style="font-size:0.8em; font-style:italic; color:var(--text-secondary);">${act.review_comment}</span>` : '';
                const sourceHtml = act.source ? `<a href="${act.source}" target="_blank" rel="noopener" class="source-link">Details ↗</a>` : '';

                activitiesHtml += `
                <li>
                    <div class="activity-header">
                        <span class="activity-name">${act.name || 'Activity'}</span>
                        <div style="font-size:0.8em; color:var(--text-secondary);">${act.schedule || ''}</div>
                        ${badgeHtml}
                    </div>
                    <div class="activity-meta" style="margin-bottom:4px; display:flex; gap:4px; align-items:center; flex-wrap:wrap;">
                        <span class="cost-tag">RM ${actCostPax}/pax</span>
                        <span style="font-size:0.8em; color:var(--text-secondary);">Total: RM ${actCostTotal}</span>
                        ${ratingHtml} ${reviewHtml} ${sourceHtml}
                    </div>
                    <div style="border-radius:6px; overflow:hidden; margin-top:4px; border:1px solid rgba(0,0,0,0.06); max-width:350px;">
                        <iframe src="${embedMap}" width="100%" height="100" style="border:0;" allowfullscreen="" loading="lazy"></iframe>
                    </div>
                </li>`;

                // Render transport connector to next activity
                const tn = act.transport_to_next;
                if (tn && actIdx < dayActivities.length - 1) {
                    const icon = modeIcon[tn.mode] || '➡️';
                    const costText = tn.estimated_cost_myr > 0 ? `RM ${tn.estimated_cost_myr}/pax` : 'Free';
                    activitiesHtml += `
                    <div class="transport-connector">
                        <span class="tc-mode">${icon}</span>
                        <div class="tc-info">
                            <span class="tc-duration">${tn.duration || ''} by ${tn.mode || 'transit'}</span>
                            ${tn.notes ? `<span class="tc-notes">${tn.notes}</span>` : ''}
                        </div>
                        <span class="tc-cost">${costText}</span>
                    </div>`;
                }
            });
        }


        // Hotel
        const hotelName = day.hotel ? day.hotel.name : 'Not Specified';
        const hotelCostPerNight = day.hotel ? day.hotel.cost_myr : 0;
        const hotelRating = day.hotel?.rating ? `<span style="color:#f5b041;">★ ${day.hotel.rating}</span>` : '';
        const hotelReview = day.hotel?.review_comment ? `<span style="font-size:0.8em; color:var(--text-secondary); font-style:italic;">"${day.hotel.review_comment}"</span>` : '';
        const hotelLink = day.hotel?.source || `https://www.google.com/maps/search/${encodeURIComponent(hotelName + ' ' + day.location)}`;
        const hotelLinkHtml = `<a href="${hotelLink}" target="_blank" rel="noopener" class="module-link">View ↗</a>`;

        // Food
        let foodRecsHtml = 'No recommendations';
        let foodCostPerPax = day.daily_food_cost_myr || 0;

        if (day.food_recommendations && Array.isArray(day.food_recommendations)) {
            if (typeof day.food_recommendations[0] === 'string') {
                foodRecsHtml = day.food_recommendations.join(', ');
            } else {
                foodRecsHtml = day.food_recommendations.map(f => {
                    const fName = f.name || '';
                    const fRating = f.rating ? `<span style="color:#f5b041;">★ ${f.rating}</span>` : '';
                    const fReview = f.review_comment ? `<span style="font-size:0.8em; color:var(--text-secondary); font-style:italic;">"${f.review_comment}"</span>` : '';
                    const fCostPax = f.avg_cost_myr || 0;
                    const fCostTag = fCostPax ? `<span class="cost-tag" style="font-size:0.75rem;">RM ${fCostPax}/pax</span>` : '';
                    const fPriceRange = f.price_range ? `<span style="font-size:0.8em; color:var(--text-secondary);">${f.price_range}</span>` : '';
                    const fLink = f.source || `https://www.google.com/maps/search/${encodeURIComponent(fName + ' ' + day.location)}`;
                    const fLinkHtml = `<a href="${fLink}" target="_blank" rel="noopener" class="module-link" style="font-size:0.8rem;">View ↗</a>`;
                    return `<div style="margin-bottom:0.3rem;"><strong>${fName}</strong> ${fRating} ${fCostTag} ${fPriceRange}<br>${fReview} ${fLinkHtml}</div>`;
                }).join('<hr style="margin:3px 0; border:0; border-top:1px solid rgba(0,0,0,0.04);">');

                let calculatedCost = day.food_recommendations.reduce((acc, f) => acc + (f.avg_cost_myr || 0), 0);
                if (calculatedCost > 0) foodCostPerPax = calculatedCost;
            }
        }
        const transRoute = day.transportation ? day.transportation.route : 'Local transit';
        const transCostPerPax = day.transportation ? day.transportation.cost_myr : 0;

        // Calculate day totals
        const dayHotelTotal = hotelCostPerNight * numPax; // hotel per night x pax (simplified)
        const dayFoodTotal = foodCostPerPax * numPax;
        const dayTransTotal = transCostPerPax * numPax;

        card.innerHTML = `
            <h4>Day ${dayNum}: ${dayLocation}</h4>
            <ul>${activitiesHtml}</ul>
            <div class="daily-modules">
                <div class="module-box">
                    <h5>Stay</h5>
                    <p>${hotelName} ${hotelRating}</p>
                    ${hotelReview}
                    ${hotelLinkHtml}
                    <span class="cost-tag">RM ${hotelCostPerNight}/night/pax</span>
                    <span style="font-size:0.75em; color:var(--text-secondary);">Total: RM ${dayHotelTotal}</span>
                </div>
                <div class="module-box">
                    <h5>Eat</h5>
                    <div style="margin-bottom:0.3rem; font-size:0.85rem;">${foodRecsHtml}</div>
                    <span class="cost-tag">RM ${foodCostPerPax}/pax/day</span>
                    <span style="font-size:0.75em; color:var(--text-secondary);">Total: RM ${dayFoodTotal}</span>
                </div>
                <div class="module-box">
                    <h5>Transit</h5>
                    <p>${transRoute}</p>
                    <span class="cost-tag">RM ${transCostPerPax}/pax/day</span>
                    <span style="font-size:0.75em; color:var(--text-secondary);">Total: RM ${dayTransTotal}</span>
                </div>
            </div>
        `;
        container.appendChild(card);
    });
}

let currentTripData = null;

function renderLedger(split, itinerary, flights, numPax) {
    numParticipants = numPax;
    if (!split || !split.primary_currency) return;
    currentTripData = { split, itinerary, flights, numPax };
    // Display total that will be reconciled when modal opens
    document.getElementById('total-cost').innerText = `RM ${split.total_myr} (${numPax} pax)`;
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
    const { split, itinerary, flights, numPax } = data;
    const n = numPax || 1;
    let hotelTotal = 0, foodTotal = 0, transTotal = 0, actTotal = 0;
    itinerary.forEach(day => {
        hotelTotal += (day.hotel ? (day.hotel.cost_myr || 0) : 0) * n;
        foodTotal += (day.daily_food_cost_myr || 0) * n;
        transTotal += (day.transportation ? (day.transportation.cost_myr || 0) : 0) * n;
        if (day.activities) day.activities.forEach(act => actTotal += (act.cost_myr || 0) * n);
    });
    const flightCostPerPax = selectedFlightOption ? (selectedFlightOption.cost_myr || 0) : (flights ? (flights.cost_myr || 0) : 0);
    const flightCostTotal = flightCostPerPax * n;

    // Compute grand total from itemized sums (source of truth for all pax)
    const grandTotal = Math.round(flightCostTotal + hotelTotal + foodTotal + transTotal + actTotal);

    document.getElementById('acc-flights').innerText = `RM ${flightCostTotal} (${n} pax × RM ${flightCostPerPax})`;
    document.getElementById('acc-hotel').innerText = `RM ${hotelTotal} (${n} pax)`;
    document.getElementById('acc-food').innerText = `RM ${foodTotal} (${n} pax)`;
    document.getElementById('acc-trans').innerText = `RM ${transTotal} (${n} pax)`;
    document.getElementById('acc-act').innerText = `RM ${actTotal} (${n} pax)`;
    // Use locally computed total — reliable for all pax regardless of LLM response
    document.getElementById('acc-total').innerText = `RM ${grandTotal} (${n} pax)`;
    // Also update the summary card total to match
    document.getElementById('total-cost').innerText = `RM ${grandTotal} (${n} pax)`;
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

// Payment
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

// PDF Generation - creates a compact print-friendly clone
document.getElementById('download-pdf-btn').addEventListener('click', () => {
    const source = document.getElementById('results-section');

    // Create a compact clone for PDF
    const clone = source.cloneNode(true);
    clone.id = 'pdf-print-area';
    clone.style.cssText = 'position:absolute; left:0; top:0; z-index:-9999; width:700px; font-size:11px; line-height:1.3; padding:10px; background:white;';
    clone.classList.remove('hidden');

    // Remove interactive elements from clone
    clone.querySelectorAll('iframe, .settlement-ui, .action-buttons-row, .flight-detail-link, .module-link, .source-link, .dest-map-link, .response-time-badge, button, input[type="radio"]').forEach(el => el.remove());

    // Shrink all card padding in clone
    clone.querySelectorAll('.glass-card').forEach(el => {
        el.style.cssText = 'padding:10px; margin-bottom:8px; border-radius:8px; border:1px solid #ddd; background:white; box-shadow:none;';
    });
    clone.querySelectorAll('.day-card').forEach(el => {
        el.style.cssText = 'padding:8px 10px; margin-bottom:6px; border-radius:6px; border:1px solid #eee; background:#fafafa;';
    });
    clone.querySelectorAll('.daily-modules').forEach(el => {
        el.style.cssText = 'display:grid; grid-template-columns:1fr 1fr 1fr; gap:6px; margin-top:6px; padding-top:6px; border-top:1px solid #eee;';
    });
    clone.querySelectorAll('.module-box').forEach(el => {
        el.style.cssText = 'padding:6px; border-radius:4px; border:1px solid #eee; background:#f8f8f8; font-size:10px;';
    });
    clone.querySelectorAll('.budget-banner').forEach(el => {
        el.style.cssText = 'padding:8px 12px; border-radius:6px; margin-bottom:8px; font-size:11px;';
    });
    clone.querySelectorAll('.destination-review').forEach(el => {
        el.style.cssText = 'padding:8px 10px; margin-bottom:6px; border-radius:6px; font-size:11px;';
    });
    clone.querySelectorAll('.flight-option-row').forEach(el => {
        el.style.cssText = 'padding:6px 8px; border:1px solid #ddd; border-radius:6px; margin-bottom:4px; background:#fafafa;';
    });
    clone.querySelectorAll('.flight-legs').forEach(el => {
        el.style.cssText = 'display:flex; gap:12px; margin-top:4px;';
    });
    clone.querySelectorAll('.flight-pricing').forEach(el => {
        el.style.cssText = 'margin-top:2px;';
    });
    clone.querySelectorAll('.split-info').forEach(el => {
        el.style.cssText = 'display:grid; grid-template-columns:1fr 1fr 1fr; gap:6px; margin-bottom:8px;';
    });
    clone.querySelectorAll('.stat-box').forEach(el => {
        el.style.cssText = 'padding:6px; border-radius:6px; text-align:center; border:1px solid #eee;';
    });
    clone.querySelectorAll('.stat-box h3').forEach(el => {
        el.style.cssText = 'font-size:14px; font-weight:700;';
    });
    clone.querySelectorAll('h2').forEach(el => {
        el.style.cssText = 'font-size:14px; margin-bottom:4px; font-weight:600;';
    });
    clone.querySelectorAll('h4').forEach(el => {
        el.style.cssText = 'font-size:12px; margin-bottom:3px; font-weight:600;';
    });
    clone.querySelectorAll('li').forEach(el => {
        el.style.cssText = 'padding:3px 0 3px 10px; font-size:10px; border-bottom:1px solid #f0f0f0;';
    });
    clone.querySelectorAll('.cost-tag').forEach(el => {
        el.style.cssText = 'display:inline; font-size:9px; padding:1px 4px; background:rgba(0,113,227,0.1); color:#0071e3; border-radius:3px; font-weight:600;';
    });
    clone.querySelectorAll('.flight-disclaimer').forEach(el => {
        el.style.cssText = 'font-size:9px; color:#888; font-style:italic; margin-top:4px; padding-top:4px; border-top:1px dashed #ddd;';
    });

    document.body.appendChild(clone);

    const opt = {
        margin: [0.3, 0.3, 0.3, 0.3],
        filename: 'DaddiesTrip_Itinerary.pdf',
        image: { type: 'jpeg', quality: 0.92 },
        html2canvas: { scale: 1.2, useCORS: true, windowWidth: 700, logging: false },
        jsPDF: { unit: 'in', format: 'a4', orientation: 'portrait' },
        pagebreak: { mode: ['avoid-all', 'css', 'legacy'] }
    };

    html2pdf().set(opt).from(clone).save().then(() => {
        document.body.removeChild(clone);
    }).catch(() => {
        if (document.body.contains(clone)) document.body.removeChild(clone);
    });
});

// ─────────────────────────────────────────────────────────────────────────────
// Feature #5: Voice Input via Web Speech API
// ─────────────────────────────────────────────────────────────────────────────
(function initVoiceInput() {
    const voiceBtn = document.getElementById('voice-btn');
    const voiceStatus = document.getElementById('voice-status');
    const promptInput = document.getElementById('prompt-input');

    // Check browser support
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        // Hide mic button gracefully — browser doesn't support it
        if (voiceBtn) voiceBtn.classList.add('hidden');
        return;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = true;        // Keep listening through pauses
    recognition.interimResults = true;    // Show live interim text
    recognition.lang = 'en-MY';           // Malaysian English
    recognition.maxAlternatives = 1;

    let isRecording = false;
    let wantToStop = false;  // User explicitly clicked stop
    let interimBase = '';    // Text already in textarea before voice started

    function setRecordingState(active) {
        isRecording = active;
        if (active) {
            voiceBtn.classList.add('recording');
            voiceBtn.querySelector('.voice-icon').textContent = '🔴';
            voiceBtn.title = 'Click to stop recording';
            voiceStatus.textContent = '🎙️ Listening... speak your trip request (click mic to stop)';
            voiceStatus.className = 'voice-status listening';
        } else {
            voiceBtn.classList.remove('recording');
            voiceBtn.querySelector('.voice-icon').textContent = '🎤';
            voiceBtn.title = 'Click to speak your trip request';
            voiceStatus.className = 'voice-status';
        }
    }

    voiceBtn.addEventListener('click', () => {
        if (isRecording) {
            wantToStop = true;
            recognition.stop();
            return;
        }
        wantToStop = false;
        interimBase = promptInput.value;
        try {
            recognition.start();
        } catch (e) {
            voiceStatus.textContent = '⚠️ Could not start microphone: ' + e.message;
            voiceStatus.className = 'voice-status error';
        }
    });

    recognition.onstart = () => {
        setRecordingState(true);
    };

    recognition.onresult = (event) => {
        let interimTranscript = '';
        let finalTranscript = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
            const transcript = event.results[i][0].transcript;
            if (event.results[i].isFinal) {
                finalTranscript += transcript;
            } else {
                interimTranscript += transcript;
            }
        }
        // Show live interim preview in textarea
        const separator = interimBase && !interimBase.endsWith(' ') && (interimTranscript || finalTranscript) ? ' ' : '';
        if (interimTranscript) {
            promptInput.value = interimBase + separator + interimTranscript;
            voiceStatus.textContent = '🎙️ ' + interimTranscript;
        }
        if (finalTranscript) {
            const combined = interimBase + separator + finalTranscript.trim();
            promptInput.value = combined;
            interimBase = combined;
            voiceStatus.textContent = '🎙️ Listening... pause is OK, keep talking';
            voiceStatus.className = 'voice-status listening';
        }
    };

    recognition.onend = () => {
        // If user didn't explicitly stop, auto-restart to tolerate pauses
        if (!wantToStop && isRecording) {
            try {
                recognition.start();
                return;  // Stay in recording state
            } catch (_) {
                // Browser refused restart — fall through to stop
            }
        }
        setRecordingState(false);
        wantToStop = false;
        if (promptInput.value.trim() && interimBase.trim()) {
            voiceStatus.textContent = '✅ Done! You can edit the text or click mic again.';
        } else if (!voiceStatus.textContent.startsWith('⚠️')) {
            voiceStatus.textContent = '';
        }
        // Auto-clear success message after 3s
        setTimeout(() => {
            if (voiceStatus.textContent.startsWith('✅')) {
                voiceStatus.textContent = '';
                voiceStatus.className = 'voice-status';
            }
        }, 3000);
    };

    recognition.onerror = (event) => {
        // "no-speech" is normal during pauses — don't stop, just let onend auto-restart
        if (event.error === 'no-speech' && !wantToStop) {
            return;  // onend will auto-restart
        }
        setRecordingState(false);
        wantToStop = false;
        const msgs = {
            'not-allowed': '⚠️ Microphone access denied. Please allow it in browser settings.',
            'no-speech':   '⚠️ No speech detected. Try speaking closer to the mic.',
            'network':     '⚠️ Network error during voice recognition.',
            'aborted':     ''
        };
        const msg = msgs[event.error] ?? `⚠️ Voice error: ${event.error}`;
        if (msg) {
            voiceStatus.textContent = msg;
            voiceStatus.className = 'voice-status error';
            setTimeout(() => { voiceStatus.textContent = ''; voiceStatus.className = 'voice-status'; }, 4000);
        }
    };
})();
