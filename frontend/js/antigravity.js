export function initAntigravity() {
    console.log("Antigravity physics initialized.");
    
    // Select elements to become physics bodies
    const targets = [
        document.querySelector('.app-header'),
        document.querySelector('.camera-card'),
        document.querySelector('.guide-card')
    ].filter(el => el !== null);

    const bodies = [];
    let isPhysicsActive = false;
    
    let mouse = { x: 0, y: 0, px: 0, py: 0, down: false };
    let dragBody = null;
    let dragOffset = { x: 0, y: 0 };
    
    // Physics constants
    const gravity = 0.4;
    const bounce = 0.75;
    const friction = 0.98;
    const groundFriction = 0.95;

    // Monitor mouse coordinates and velocities
    window.addEventListener('mousemove', (e) => {
        mouse.px = mouse.x;
        mouse.py = mouse.y;
        mouse.x = e.clientX;
        mouse.y = e.clientY;
        
        if (mouse.down && dragBody) {
            dragBody.x = mouse.x - dragOffset.x;
            dragBody.y = mouse.y - dragOffset.y;
            dragBody.vx = mouse.x - mouse.px;
            dragBody.vy = mouse.y - mouse.py;
        }
    });

    window.addEventListener('mousedown', (e) => {
        mouse.down = true;
        // Check if mouse is over any body
        for (let body of bodies) {
            if (mouse.x >= body.x && mouse.x <= body.x + body.width &&
                mouse.y >= body.y && mouse.y <= body.y + body.height) {
                dragBody = body;
                body.isDragging = true;
                dragOffset.x = mouse.x - body.x;
                dragOffset.y = mouse.y - body.y;
                body.vx = 0;
                body.vy = 0;
                break;
            }
        }
    });

    window.addEventListener('mouseup', () => {
        mouse.down = false;
        if (dragBody) {
            dragBody.isDragging = false;
            dragBody = null;
        }
    });

    // Detaches elements from document flow and assigns physics states
    function startPhysics() {
        if (isPhysicsActive) return;
        isPhysicsActive = true;
        
        // Save initial absolute positions before detaching
        targets.forEach((el) => {
            const rect = el.getBoundingClientRect();
            
            // Set styles to absolute
            el.style.position = 'fixed';
            el.style.width = `${rect.width}px`;
            el.style.height = `${rect.height}px`;
            el.style.left = '0';
            el.style.top = '0';
            el.style.zIndex = '1000';
            el.style.margin = '0';
            el.style.cursor = 'grab';
            
            bodies.push({
                element: el,
                x: rect.left,
                y: rect.top,
                vx: (Math.random() - 0.5) * 10,
                vy: (Math.random() - 0.5) * 10,
                width: rect.width,
                height: rect.height,
                mass: (rect.width * rect.height) / 5000,
                isDragging: false
            });
        });
        
        // Hide background blobs to avoid visual noise
        const blobs = document.querySelector('.glass-bg-blobs');
        if (blobs) blobs.style.display = 'none';

        physicsLoop();
    }

    // Resolve elastic collisions between rectangle bodies
    function resolveCollisions() {
        for (let i = 0; i < bodies.length; i++) {
            const b1 = bodies[i];
            for (let j = i + 1; j < bodies.length; j++) {
                const b2 = bodies[j];
                
                // AABB overlap check
                const overlapX = Math.min(b1.x + b1.width, b2.x + b2.width) - Math.max(b1.x, b2.x);
                const overlapY = Math.min(b1.y + b1.height, b2.y + b2.height) - Math.max(b1.y, b2.y);
                
                if (overlapX > 0 && overlapY > 0) {
                    // Push apart on the axis of least penetration
                    if (overlapX < overlapY) {
                        const push = overlapX / 2;
                        if (b1.x < b2.x) {
                            if (!b1.isDragging) b1.x -= push;
                            if (!b2.isDragging) b2.x += push;
                        } else {
                            if (!b1.isDragging) b1.x += push;
                            if (!b2.isDragging) b2.x -= push;
                        }
                        // Swap X velocities with simple elastic bounce
                        const temp = b1.vx;
                        b1.vx = b2.vx * bounce;
                        b2.vx = temp * bounce;
                    } else {
                        const push = overlapY / 2;
                        if (b1.y < b2.y) {
                            if (!b1.isDragging) b1.y -= push;
                            if (!b2.isDragging) b2.y += push;
                        } else {
                            if (!b1.isDragging) b1.y += push;
                            if (!b2.isDragging) b2.y -= push;
                        }
                        // Swap Y velocities with simple elastic bounce
                        const temp = b1.vy;
                        b1.vy = b2.vy * bounce;
                        b2.vy = temp * bounce;
                    }
                }
            }
        }
    }

    function physicsLoop() {
        if (!isPhysicsActive) return;
        requestAnimationFrame(physicsLoop);

        const w = window.innerWidth;
        const h = window.innerHeight;

        bodies.forEach((body) => {
            if (body.isDragging) {
                // Keep element inside browser limits during dragging
                body.x = Math.max(0, Math.min(w - body.width, body.x));
                body.y = Math.max(0, Math.min(h - body.height, body.y));
                
                body.element.style.transform = `translate3d(${body.x}px, ${body.y}px, 0)`;
                body.element.style.cursor = 'grabbing';
                return;
            }

            // Apply gravity and friction
            body.vy += gravity;
            body.vx *= friction;
            body.vy *= friction;

            // Update coordinate positions
            body.x += body.vx;
            body.y += body.vy;

            // Bounding collision: Floor
            if (body.y + body.height > h) {
                body.y = h - body.height;
                body.vy = -body.vy * bounce;
                body.vx *= groundFriction; // slide deceleration
            }
            
            // Bounding collision: Ceiling
            if (body.y < 0) {
                body.y = 0;
                body.vy = -body.vy * bounce;
            }

            // Bounding collision: Right Wall
            if (body.x + body.width > w) {
                body.x = w - body.width;
                body.vx = -body.vx * bounce;
            }

            // Bounding collision: Left Wall
            if (body.x < 0) {
                body.x = 0;
                body.vx = -body.vx * bounce;
            }

            // Apply style transformation matrix
            body.element.style.transform = `translate3d(${body.x}px, ${body.y}px, 0)`;
            body.element.style.cursor = 'grab';
        });

        resolveCollisions();
    }

    return {
        activate: startPhysics
    };
}
