// --- LUXURY BRAND SVG LOGOS ---
// All paths are drawn to fit nicely in a 100x100 viewBox.
// Since we use mix-blend-mode: difference, the SVG fills are white, appearing inverted on light sections.
const BRAND_LOGOS = {
    chanel: {
        name: "Chanel",
        svgPath: `
            <!-- Interlocking Double C -->
            <!-- Left C -->
            <path d="M 45,50 C 45,38.9 36.1,30 25,30 C 13.9,30 5,38.9 5,50 C 5,61.1 13.9,70 25,70 C 36.1,70 45,61.1 45,50 M 35,50 C 35,55.5 30.5,60 25,60 C 19.5,60 15,55.5 15,50 C 15,44.5 19.5,40 25,40 C 30.5,40 35,44.5 35,50 Z" fill-rule="evenodd" />
            <!-- Right C -->
            <path d="M 95,50 C 95,38.9 86.1,30 75,30 C 63.9,30 55,38.9 55,50 C 55,61.1 63.9,70 75,70 C 86.1,70 95,61.1 95,50 M 85,50 C 85,55.5 80.5,60 75,60 C 69.5,60 65,55.5 65,50 C 65,44.5 69.5,40 75,40 C 80.5,40 85,44.5 85,50 Z" fill-rule="evenodd" />
        `
    },
    hermes: {
        name: "Hermès",
        svgPath: `
            <!-- Minimalistic Serif H & Carriage Concept -->
            <!-- Outer Ring -->
            <circle cx="50" cy="50" r="46" fill="none" stroke="currentColor" stroke-width="2" />
            <!-- Center H -->
            <path d="M 32,25 L 42,25 M 37,25 L 37,75 M 32,75 L 42,75 
                     M 58,25 L 68,25 M 63,25 L 63,75 M 58,75 L 68,75 
                     M 37,50 L 63,50" stroke="currentColor" stroke-width="4" stroke-linecap="square" fill="none" />
        `
    },
    gucci: {
        name: "Gucci",
        svgPath: `
            <!-- Interlocking G Monogram -->
            <!-- Left G -->
            <path d="M 45,50 C 45,39 36,30 25,30 C 14,30 5,39 5,50 C 5,61 14,70 25,70 C 36,70 45,61 45,50 M 35,50 C 35,55.5 30.5,60 25,60 C 19.5,60 15,55.5 15,50 C 15,44.5 19.5,40 25,40 C 30.5,40 35,44.5 35,50 Z" fill-rule="evenodd" />
            <!-- Right G (Inverted) -->
            <path d="M 95,50 C 95,39 86,30 75,30 C 64,30 55,39 55,50 C 55,61 64,70 75,70 C 86,70 95,61 95,50 M 85,50 C 85,55.5 80.5,60 75,60 C 69.5,60 65,55.5 65,50 C 65,44.5 69.5,40 75,40 C 80.5,40 85,44.5 85,50 Z" fill-rule="evenodd" />
            <!-- Crossbar extensions representing the Gs -->
            <path d="M 25,50 H 42 M 75,50 H 58" stroke="currentColor" stroke-width="4" />
        `
    },
    prada: {
        name: "Prada",
        svgPath: `
            <!-- Iconic Prada Triangle & P -->
            <!-- Triangle Outline -->
            <polygon points="50,15 90,80 10,80" fill="none" stroke="currentColor" stroke-width="3" />
            <polygon points="50,22 83,75 17,75" fill="none" stroke="currentColor" stroke-width="1" />
            <!-- Stylized 'P' Monogram in Center -->
            <path d="M 45,38 H 55 C 59,38 61,40 61,44 C 61,48 59,50 55,50 H 45 V 65 M 50,50 V 38 M 45,46 H 55" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="square" />
        `
    },
    louisvuitton: {
        name: "Louis Vuitton",
        svgPath: `
            <!-- Interlocking L & V -->
            <!-- The 'L' (Slanted) -->
            <path d="M 28,68 L 38,30 H 44 L 36,62 H 58 L 56,68 Z" />
            <!-- The 'V' (Interlocking) -->
            <path d="M 46,30 L 59,68 H 65 L 78,30 H 70 L 62,56 L 54,30 Z" />
        `
    },
    dior: {
        name: "Dior",
        svgPath: `
            <!-- Stylized Dior Star and typography -->
            <!-- Central Star -->
            <path d="M 50,20 L 53,35 L 68,35 L 56,44 L 60,59 L 50,50 L 40,59 L 44,44 L 32,35 L 47,35 Z" />
            <!-- Typographic base circle -->
            <circle cx="50" cy="50" r="42" fill="none" stroke="currentColor" stroke-width="1.5" stroke-dasharray="2, 6" />
            <circle cx="50" cy="50" r="32" fill="none" stroke="currentColor" stroke-width="1" />
        `
    }
};

// --- GLOBAL VARIABLES & STATE ---
let selectedBrandKey = 'chanel';
const mousePos = { x: 0, y: 0 };
const cursorPos = { x: 0, y: 0 };
const cursorSpeed = 0.15; // Speed multiplier for lag (lerp)

// Analytics Chart Data
const chartData = {
    months: ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
    brands: {
        chanel: [78, 80, 81, 83, 82, 84.2],
        hermes: [88, 89.5, 90, 91.2, 90.8, 91.2],
        gucci: [68, 67, 69.5, 68.2, 66, 64.5]
    },
    categories: [
        { label: "Leather Goods", percentage: 40, color: "#111" },
        { label: "Ready-To-Wear", percentage: 35, color: "#767676" },
        { label: "Fine Jewelry", percentage: 15, color: "#C5A059" },
        { label: "Footwear", percentage: 10, color: "#E5E5E5" }
    ]
};

// --- INITIALIZATION ---
window.addEventListener('DOMContentLoaded', () => {
    // 1. Set current date in editorial header
    formatCurrentDate();

    // 2. Load random luxury cursor
    selectRandomCursor();

    // 3. Initialize custom cursor tracking
    initCustomCursor();

    // 4. Initialize section routing tabs
    initSectionRouting();

    // 5. Render analytics charts
    renderLineChart();
    renderDonutChart();

    // 6. Start live counters
    initLiveStats();
});

// --- DATE FORMATTER ---
function formatCurrentDate() {
    const dateEl = document.getElementById('current-date');
    if (!dateEl) return;
    
    const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
    const today = new Date();
    dateEl.innerText = today.toLocaleDateString('en-US', options).toUpperCase();
}

// --- CURSOR LOGIC ---
function selectRandomCursor() {
    const brandKeys = Object.keys(BRAND_LOGOS);
    const randomIndex = Math.floor(Math.random() * brandKeys.length);
    selectedBrandKey = brandKeys[randomIndex];
    const brand = BRAND_LOGOS[selectedBrandKey];

    const cursorSvg = document.getElementById('cursor-svg');
    if (cursorSvg) {
        cursorSvg.innerHTML = brand.svgPath;
        // Print active luxury logo cursor in console for confirmation
        console.log(`%c Orbital Fashion: Loaded luxury cursor logo for ${brand.name} `, "background: #000; color: #fff; font-weight: bold; padding: 4px;");
    }
}

function initCustomCursor() {
    const cursor = document.getElementById('custom-cursor');
    if (!cursor) return;

    // Track real mouse position
    window.addEventListener('mousemove', (e) => {
        mousePos.x = e.clientX;
        mousePos.y = e.clientY;
    });

    // Smooth cursor interpolation (lerp)
    function updateCursor() {
        // Calculate distance towards target
        const dx = mousePos.x - cursorPos.x;
        const dy = mousePos.y - cursorPos.y;
        
        // Add fraction of distance to make it lag smoothly
        cursorPos.x += dx * cursorSpeed;
        cursorPos.y += dy * cursorSpeed;
        
        cursor.style.transform = `translate3d(${cursorPos.x}px, ${cursorPos.y}px, 0)`;
        
        requestAnimationFrame(updateCursor);
    }
    requestAnimationFrame(updateCursor);

    // Hover state over interactive elements
    const hoverables = document.querySelectorAll('a, button, input, select, textarea, [role="button"], .table-row-hover');
    hoverables.forEach(el => {
        el.addEventListener('mouseenter', () => {
            cursor.classList.add('hovered');
        });
        el.addEventListener('mouseleave', () => {
            cursor.classList.remove('hovered');
        });
    });

    // Temporarily hide cursor when leaving window
    document.addEventListener('mouseleave', () => {
        cursor.style.opacity = '0';
    });
    document.addEventListener('mouseenter', () => {
        cursor.style.opacity = '1';
    });
}

// --- NAVIGATION & TABS ---
function initSectionRouting() {
    const navLinks = document.querySelectorAll('.nav-link');
    const sections = document.querySelectorAll('.vogue-section');
    const footerLinks = document.querySelectorAll('.vogue-footer a');

    // Combine header nav links and footer links
    const allRoutes = [...navLinks, ...footerLinks];

    allRoutes.forEach(link => {
        link.addEventListener('click', (e) => {
            // Check if it's an internal hash link
            const targetId = link.getAttribute('href').substring(1);
            const targetSection = document.getElementById(targetId);
            
            if (targetSection) {
                e.preventDefault();

                // Remove active classes
                sections.forEach(sec => sec.classList.remove('active'));
                navLinks.forEach(nl => nl.classList.remove('active'));

                // Add active class to target section
                targetSection.classList.add('active');
                
                // Add active class to matching nav link
                const matchingNavLink = document.querySelector(`.nav-link[data-section="${targetId}"]`);
                if (matchingNavLink) {
                    matchingNavLink.classList.add('active');
                }

                // Scroll to top
                window.scrollTo({
                    top: 0,
                    behavior: 'smooth'
                });

                // Re-render charts if transitioning to Engagement section to trigger animations
                if (targetId === 'engagement') {
                    // Small delay to let section render before drawing
                    setTimeout(() => {
                        renderLineChart();
                        renderDonutChart();
                    }, 50);
                }
            }
        });
    });
}

// --- REAL-TIME DATA SIMULATION (ENGAGEMENT SECTION) ---
function initLiveStats() {
    const swapCounter = document.getElementById('live-swap-counter');
    const co2Counter = document.getElementById('live-co2-counter');
    const refreshBtn = document.getElementById('refresh-dashboard-btn');

    let swapCount = 142850;
    let co2Count = 1842.50;

    // Simulate minor live activity increments every 3.5 seconds
    setInterval(() => {
        const swapInc = Math.floor(Math.random() * 8) + 1;
        const co2Inc = parseFloat((Math.random() * 0.12).toFixed(2));

        swapCount += swapInc;
        co2Count += co2Inc;

        if (swapCounter) swapCounter.innerText = swapCount.toLocaleString();
        if (co2Counter) co2Counter.innerText = co2Count.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }, 3500);

    // Refresh button event listener
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            refreshBtn.innerText = "REFRESHING...";
            refreshBtn.disabled = true;

            // Trigger re-render with small delay
            setTimeout(() => {
                swapCount += Math.floor(Math.random() * 150) + 50;
                co2Count += parseFloat((Math.random() * 8.5).toFixed(2));
                
                if (swapCounter) swapCounter.innerText = swapCount.toLocaleString();
                if (co2Counter) co2Counter.innerText = co2Count.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

                renderLineChart();
                renderDonutChart();

                refreshBtn.innerText = "REFRESH DATA FEED";
                refreshBtn.disabled = false;
            }, 1000);
        });
    }
}

// --- CUSTOM CANVAS LINE CHART DRAWING ---
function renderLineChart() {
    const canvas = document.getElementById('indexTrendChart');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    
    // Handle Retina displays by doubling size and scaling back with CSS
    const width = canvas.parentElement.clientWidth;
    const height = 250;
    canvas.width = width * 2;
    canvas.height = height * 2;
    canvas.style.width = width + 'px';
    canvas.style.height = height + 'px';
    
    ctx.scale(2, 2);

    // Setup coordinates margins
    const padding = { top: 30, right: 30, bottom: 40, left: 40 };
    const graphWidth = width - padding.left - padding.right;
    const graphHeight = height - padding.top - padding.bottom;

    // Clear canvas
    ctx.clearRect(0, 0, width, height);

    // Find min and max for scaling Y-axis
    const allValues = [
        ...chartData.brands.chanel,
        ...chartData.brands.hermes,
        ...chartData.brands.gucci
    ];
    const minY = Math.floor(Math.min(...allValues) - 5);
    const maxY = Math.ceil(Math.max(...allValues) + 5);

    // Draw horizontal grid lines & Y-axis labels
    const gridRows = 4;
    ctx.strokeStyle = '#E5E5E5';
    ctx.lineWidth = 1;
    ctx.fillStyle = '#767676';
    ctx.font = '300 10px Montserrat';
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';

    for (let i = 0; i <= gridRows; i++) {
        const yVal = minY + ((maxY - minY) / gridRows) * i;
        const yPos = padding.top + graphHeight - (graphHeight / gridRows) * i;
        
        // Draw grid line
        ctx.beginPath();
        ctx.moveTo(padding.left, yPos);
        ctx.lineTo(padding.left + graphWidth, yPos);
        ctx.stroke();

        // Draw label
        ctx.fillText(yVal.toFixed(0) + '%', padding.left - 10, yPos);
    }

    // Draw X-axis labels (months)
    const pointsCount = chartData.months.length;
    const stepX = graphWidth / (pointsCount - 1);
    
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    ctx.fillStyle = '#767676';

    chartData.months.forEach((month, idx) => {
        const xPos = padding.left + idx * stepX;
        ctx.fillText(month, xPos, padding.top + graphHeight + 10);
    });

    // Helper: Map data coordinates to Canvas coordinates
    function getCoords(index, percentageValue) {
        const x = padding.left + index * stepX;
        const y = padding.top + graphHeight - ((percentageValue - minY) / (maxY - minY)) * graphHeight;
        return { x, y };
    }

    // Draw lines for each brand
    const drawLine = (data, strokeColor, lineWidth = 2) => {
        ctx.beginPath();
        ctx.strokeStyle = strokeColor;
        ctx.lineWidth = lineWidth;
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';

        data.forEach((val, idx) => {
            const coords = getCoords(idx, val);
            if (idx === 0) {
                ctx.moveTo(coords.x, coords.y);
            } else {
                // Bezier curve approximation
                const prevCoords = getCoords(idx - 1, data[idx - 1]);
                const cpX1 = prevCoords.x + stepX / 2;
                const cpY1 = prevCoords.y;
                const cpX2 = coords.x - stepX / 2;
                const cpY2 = coords.y;
                ctx.bezierCurveTo(cpX1, cpY1, cpX2, cpY2, coords.x, coords.y);
            }
        });
        ctx.stroke();

        // Draw points
        data.forEach((val, idx) => {
            const coords = getCoords(idx, val);
            ctx.beginPath();
            ctx.arc(coords.x, coords.y, 4, 0, 2 * Math.PI);
            ctx.fillStyle = '#FFFFFF';
            ctx.fill();
            ctx.strokeStyle = strokeColor;
            ctx.lineWidth = 2;
            ctx.stroke();
        });
    };

    // Draw lines (LV/Chanel/Hermes/Gucci representation)
    drawLine(chartData.brands.hermes, '#E65A28', 2); // Hermès Orange
    drawLine(chartData.brands.chanel, '#000000', 2); // Chanel Black
    drawLine(chartData.brands.gucci, '#006643', 2);  // Gucci Green
}

// --- CUSTOM CANVAS DONUT CHART DRAWING ---
function renderDonutChart() {
    const canvas = document.getElementById('categoryShareChart');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    
    // Handle Retina
    const width = 250;
    const height = 250;
    canvas.width = width * 2;
    canvas.height = height * 2;
    canvas.style.width = width + 'px';
    canvas.style.height = height + 'px';
    
    ctx.scale(2, 2);

    const centerX = width / 2;
    const centerY = height / 2;
    const outerRadius = 80;
    const innerRadius = 55;

    // Clear canvas
    ctx.clearRect(0, 0, width, height);

    // Track current angle
    let currentAngle = -Math.PI / 2; // Start from top 12 o'clock

    // Draw segments
    chartData.categories.forEach(category => {
        const sliceAngle = (category.percentage / 100) * (2 * Math.PI);
        const endAngle = currentAngle + sliceAngle;

        ctx.beginPath();
        ctx.arc(centerX, centerY, outerRadius, currentAngle, endAngle);
        ctx.arc(centerX, centerY, innerRadius, endAngle, currentAngle, true); // Inner ring reversed
        ctx.closePath();
        
        ctx.fillStyle = category.color;
        ctx.fill();

        // Track next starting position
        currentAngle = endAngle;
    });

    // Draw Center text details (Editorial look)
    ctx.fillStyle = '#000000';
    ctx.font = 'bold 16px Playfair Display';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText("SHARE", centerX, centerY - 10);

    ctx.fillStyle = '#767676';
    ctx.font = '500 9px Montserrat';
    ctx.fillText("Q2 2026", centerX, centerY + 10);

    // Optional: Draw floating custom key label texts around
    // Let's create legend dynamically below or custom overlay inside HTML instead of cluttered canvas labels.
    // For pure styling, we'll draw legend keys beneath the canvas wrapper. Let's append if legend element doesn't exist.
    let legendContainer = canvas.nextElementSibling;
    if (!legendContainer || !legendContainer.classList.contains('donut-legend')) {
        legendContainer = document.createElement('div');
        legendContainer.className = 'donut-legend';
        
        // Add basic custom layout styling to donut-legend
        legendContainer.style.marginTop = '20px';
        legendContainer.style.display = 'grid';
        legendContainer.style.gridTemplateColumns = '1fr 1fr';
        legendContainer.style.gap = '10px';
        legendContainer.style.fontSize = '0.75rem';
        legendContainer.style.fontWeight = '300';
        
        chartData.categories.forEach(cat => {
            const item = document.createElement('div');
            item.className = 'donut-legend-item';
            item.style.display = 'flex';
            item.style.alignItems = 'center';
            item.style.gap = '8px';

            const colorSquare = document.createElement('span');
            colorSquare.style.width = '10px';
            colorSquare.style.height = '10px';
            colorSquare.style.backgroundColor = cat.color;
            colorSquare.style.borderRadius = '2px';
            colorSquare.style.display = 'inline-block';

            const textSpan = document.createElement('span');
            textSpan.innerHTML = `<strong>${cat.percentage}%</strong> ${cat.label}`;

            item.appendChild(colorSquare);
            item.appendChild(textSpan);
            legendContainer.appendChild(item);
        });

        canvas.parentNode.appendChild(legendContainer);
    }
}
