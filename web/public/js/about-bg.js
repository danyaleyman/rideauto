/**
 * Анимированный фон для about.html: «дорога», сетка и силуэты авто в цветах сайта.
 */
(function () {
  var canvas = document.getElementById('aboutBgCanvas');
  if (!canvas || !canvas.getContext) return;

  if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    canvas.style.display = 'none';
    return;
  }

  var ctx = canvas.getContext('2d');
  var px = Math.min(window.devicePixelRatio || 1, 2);
  var w = 0;
  var h = 0;
  var cars = [];
  var last = performance.now();

  function resize() {
    w = window.innerWidth;
    h = window.innerHeight;
    canvas.width = Math.floor(w * px);
    canvas.height = Math.floor(h * px);
    canvas.style.width = w + 'px';
    canvas.style.height = h + 'px';
    ctx.setTransform(px, 0, 0, px, 0, 0);
  }

  function spawnCar() {
    return {
      x: -100 - Math.random() * 180,
      yN: 0.18 + Math.random() * 0.64,
      cw: 36 + Math.random() * 32,
      ch: 12 + Math.random() * 10,
      spd: 55 + Math.random() * 110,
      hue: 200 + Math.random() * 50
    };
  }

  function ensureCars() {
    var target = Math.min(16, Math.max(8, Math.floor(w / 90)));
    while (cars.length < target) cars.push(spawnCar());
    while (cars.length > target) cars.pop();
  }

  function roundRectPath(x, y, cw, ch, r) {
    r = Math.min(r, cw / 2, ch / 2);
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + cw - r, y);
    ctx.quadraticCurveTo(x + cw, y, x + cw, y + r);
    ctx.lineTo(x + cw, y + ch - r);
    ctx.quadraticCurveTo(x + cw, y + ch, x + cw - r, y + ch);
    ctx.lineTo(x + r, y + ch);
    ctx.quadraticCurveTo(x, y + ch, x, y + ch - r);
    ctx.lineTo(x, y + r);
    ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.closePath();
  }

  function drawFrame(now) {
    var dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    var t = now * 0.001;

    var g = ctx.createLinearGradient(0, 0, w, h);
    g.addColorStop(0, '#eff6ff');
    g.addColorStop(0.4, '#f8fafc');
    g.addColorStop(1, '#e2e8f0');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, w, h);

    var off = (t * 45) % 100;
    ctx.strokeStyle = 'rgba(59, 130, 246, 0.14)';
    ctx.lineWidth = 1.5;
    for (var i = -3; i < 18; i++) {
      var x0 = i * 100 - off;
      ctx.beginPath();
      ctx.moveTo(x0, h * 0.2);
      ctx.lineTo(x0 + h * 0.42, h + 20);
      ctx.stroke();
    }

    ctx.setLineDash([14, 18]);
    ctx.lineDashOffset = -t * 28;
    ctx.strokeStyle = 'rgba(59, 130, 246, 0.22)';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(w * 0.5, h * 0.22);
    ctx.lineTo(w * 0.5, h + 10);
    ctx.stroke();
    ctx.setLineDash([]);

    var gs = 56;
    var gx = (t * 18) % gs;
    ctx.fillStyle = 'rgba(59, 130, 246, 0.055)';
    for (var gx0 = -gs; gx0 < w + gs; gx0 += gs) {
      for (var gy = 0; gy < h; gy += gs) {
        ctx.fillRect(gx0 + gx, gy, 1.5, 1.5);
      }
    }

    for (var c = 0; c < cars.length; c++) {
      var car = cars[c];
      car.x += car.spd * dt;
      if (car.x > w + 60) {
        cars[c] = spawnCar();
        car = cars[c];
      }
      var cy = car.yN * h;
      ctx.fillStyle = 'rgba(55, 65, 81, 0.22)';
      roundRectPath(car.x, cy, car.cw, car.ch, 5);
      ctx.fill();
      ctx.fillStyle = 'hsla(' + car.hue + ', 62%, 52%, 0.4)';
      roundRectPath(car.x + car.cw * 0.12, cy + car.ch * 0.22, car.cw * 0.76, car.ch * 0.56, 3);
      ctx.fill();
    }

    requestAnimationFrame(drawFrame);
  }

  window.addEventListener('resize', function () {
    resize();
    ensureCars();
  });
  resize();
  ensureCars();
  requestAnimationFrame(drawFrame);
})();
