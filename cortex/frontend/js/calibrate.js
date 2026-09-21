/**
 * CORTEX — Node Position Calibrator
 * Open browser console and run: enableCalibration()
 * Then drag any node to the exact apple position.
 * Run: getPositions() to copy final values.
 */
function enableCalibration() {
  console.log('%c🍎 CORTEX Node Calibrator ON', 'color:#d4e8a0;font-size:16px;font-weight:bold');
  console.log('Drag any node to fine-tune its position. Run getPositions() when done.');

  document.querySelectorAll('.apple-node').forEach(node => {
    node.style.cursor = 'grab';
    node.draggable = false;

    let startX, startY, startLeft, startTop;

    node.addEventListener('mousedown', e => {
      e.stopPropagation();
      const rect = node.parentElement.getBoundingClientRect();
      startX    = e.clientX;
      startY    = e.clientY;
      startLeft = parseFloat(node.style.left);
      startTop  = parseFloat(node.style.top);
      node.style.cursor = 'grabbing';
      node.style.zIndex = 99;

      const onMove = ev => {
        const dx = ((ev.clientX - startX) / rect.width)  * 100;
        const dy = ((ev.clientY - startY) / rect.height) * 100;
        node.style.left = `${(startLeft + dx).toFixed(1)}%`;
        node.style.top  = `${(startTop  + dy).toFixed(1)}%`;
      };

      const onUp = () => {
        node.style.cursor = 'grab';
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup',   onUp);
      };

      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup',   onUp);
    });
  });
}

function getPositions() {
  const result = {};
  document.querySelectorAll('.apple-node').forEach(n => {
    result[n.dataset.agent] = { left: n.style.left, top: n.style.top };
  });
  console.log('%cNode Positions:', 'color:#d4e8a0;font-weight:bold');
  console.log(JSON.stringify(result, null, 2));
  return result;
}

window.enableCalibration = enableCalibration;
window.getPositions = getPositions;
