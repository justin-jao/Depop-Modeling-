// --- CLOTHING ITEM SVG CURSORS (UNTRADEMARKED) ---
// All paths fit in a 100x100 viewBox.
// Since we use mix-blend-mode: difference, the SVG fills/strokes are white (inverting on sections).
const CLOTHING_ITEMS = {
    hanger: {
        name: "Hanger",
        svgPath: `
            <!-- Clothing Hanger -->
            <path d="M 50,18 C 55,18 58,22 58,26 C 58,31 54,33 50,36 L 50,44 M 50,44 L 85,63 C 87,64 85,67 82,67 H 18 C 15,67 13,64 15,63 Z" fill="none" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" />
        `
    },
    tshirt: {
        name: "T-Shirt",
        svgPath: `
            <!-- Flat-lay T-Shirt -->
            <path d="M 34,22 C 40,26 45,26 50,26 C 55,26 60,26 66,22 L 82,32 C 84,33 84,36 82,38 L 76,44 C 74,46 72,45 72,42 L 72,75 C 72,78 69,80 66,80 H 34 C 31,80 28,78 28,75 L 28,42 C 28,45 26,46 24,44 L 18,38 C 16,36 16,33 18,32 Z" fill="none" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" />
        `
    },
    dress: {
        name: "Dress",
        svgPath: `
            <!-- Slip Dress Gown -->
            <path d="M 36,20 L 39,32 M 64,20 L 61,32" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" />
            <path d="M 39,32 C 45,35 55,35 61,32 L 65,55 C 67,65 74,78 78,84 H 22 C 26,78 33,65 35,55 Z" fill="none" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" />
        `
    },
    shoe: {
        name: "High Heel",
        svgPath: `
            <!-- Stiletto Pump Heel -->
            <path d="M 15,75 C 20,75 32,74 42,66 L 70,35 C 75,30 81,30 85,35 C 89,40 88,46 83,52 L 64,68 C 55,75 48,75 42,75 M 64,65 V 82" fill="none" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" />
        `
    },
    hat: {
        name: "Wide-Brim Hat",
        svgPath: `
            <!-- Editorial Hat -->
            <path d="M 15,65 C 15,60 85,60 85,65 C 85,70 15,70 15,65 Z" fill="none" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" />
            <path d="M 32,62 C 32,45 38,30 50,30 C 62,30 68,45 68,62" fill="none" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" />
            <path d="M 32,58 C 45,60 55,60 68,58" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" />
        `
    },
    tote: {
        name: "Tote Bag",
        svgPath: `
            <!-- Minimalist Tote Bag -->
            <path d="M 28,45 H 72 V 80 C 72,83 69,85 66,85 H 34 C 31,85 28,83 28,80 Z" fill="none" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" />
            <path d="M 38,45 C 38,25 45,20 50,20 C 55,20 62,25 62,45" fill="none" stroke="currentColor" stroke-width="4" stroke-linecap="round" />
        `
    }
};

// --- GLOBAL VARIABLES & STATE ---
let selectedItemKey = 'hanger';
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
    const keys = Object.keys(CLOTHING_ITEMS);
    const randomIndex = Math.floor(Math.random() * keys.length);
    selectedItemKey = keys[randomIndex];
    const item = CLOTHING_ITEMS[selectedItemKey];

    const cursorSvg = document.getElementById('cursor-svg');
    if (cursorSvg) {
        cursorSvg.innerHTML = item.svgPath;
        // Print active cursor item in console for confirmation
        console.log(`%c Orbital Fashion: Loaded cursor shape for ${item.name} `, "background: #000; color: #fff; font-weight: bold; padding: 4px;");
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
