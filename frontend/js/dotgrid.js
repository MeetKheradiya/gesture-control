export function initDotGrid(canvas) {
    const ctx = canvas.getContext('2d');
    
    let dots = [];
    const spacing = 32;     // Space between dots
    const baseRadius = 1.2; // Base dot size
    const maxRadius = 3.0;  // Max dot size when hovered
    const glowRadius = 160; // Influence circle size
    
    let mouse = { x: -1000, y: -1000, active: false };
    let width = 0;
    let height = 0;
    
    // Color Palette
    const dotColor = 'rgba(255, 255, 255, 0.08)'; // Dim ambient dots
    
    function resize() {
        width = canvas.width = window.innerWidth;
        height = canvas.height = window.innerHeight;
    }
    
    window.addEventListener('resize', resize);
    resize();
    
    // Tracks mouse movement
    window.addEventListener('mousemove', (e) => {
        mouse.x = e.clientX;
        mouse.y = e.clientY;
        mouse.active = true;
    });
    
    window.addEventListener('mouseleave', () => {
        mouse.active = false;
        mouse.x = -1000;
        mouse.y = -1000;
    });
    
    // Touch support for mobile devices
    window.addEventListener('touchmove', (e) => {
        if (e.touches.length > 0) {
            mouse.x = e.touches[0].clientX;
            mouse.y = e.touches[0].clientY;
            mouse.active = true;
        }
    }, { passive: true });
    
    window.addEventListener('touchend', () => {
        mouse.active = false;
        mouse.x = -1000;
        mouse.y = -1000;
    });

    function draw() {
        ctx.clearRect(0, 0, width, height);
        
        const cols = Math.ceil(width / spacing);
        const rows = Math.ceil(height / spacing);
        
        // Offset to center the grid
        const startX = (width % spacing) / 2;
        const startY = (height % spacing) / 2;
        
        for (let c = 0; c <= cols; c++) {
            for (let r = 0; r <= rows; r++) {
                const x = startX + c * spacing;
                const y = startY + r * spacing;
                
                // Calculate distance to cursor
                const dx = x - mouse.x;
                const dy = y - mouse.y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                
                if (mouse.active && dist < glowRadius) {
                    // Proximity factor (1 at center, 0 at border)
                    const factor = 1 - (dist / glowRadius);
                    
                    // Draw a radial color glow behind dots
                    ctx.save();
                    const glowGrad = ctx.createRadialGradient(x, y, 0, x, y, spacing * 1.5);
                    // Proximity blends cyan (#00f2fe) into purple (#9b51e0)
                    glowGrad.addColorStop(0, `rgba(0, 242, 254, ${0.18 * factor})`);
                    glowGrad.addColorStop(0.5, `rgba(155, 81, 224, ${0.10 * factor})`);
                    glowGrad.addColorStop(1, 'rgba(0, 0, 0, 0)');
                    ctx.fillStyle = glowGrad;
                    ctx.beginPath();
                    ctx.arc(x, y, spacing * 1.5, 0, Math.PI * 2);
                    ctx.fill();
                    ctx.restore();
                    
                    // Draw glowing dot
                    const radius = baseRadius + (maxRadius - baseRadius) * factor;
                    const dotGrad = ctx.createLinearGradient(x - radius, y - radius, x + radius, y + radius);
                    dotGrad.addColorStop(0, '#00f2fe'); // Cyan
                    dotGrad.addColorStop(1, '#9b51e0'); // Purple
                    
                    ctx.fillStyle = dotGrad;
                    ctx.beginPath();
                    ctx.arc(x, y, radius, 0, Math.PI * 2);
                    ctx.fill();
                } else {
                    // Draw standard ambient dot
                    ctx.fillStyle = dotColor;
                    ctx.beginPath();
                    ctx.arc(x, y, baseRadius, 0, Math.PI * 2);
                    ctx.fill();
                }
            }
        }
        
        requestAnimationFrame(draw);
    }
    
    // Start drawing loop
    draw();
    
    return {
        dispose: () => {
            window.removeEventListener('resize', resize);
        }
    };
}
