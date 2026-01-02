/**
 * Rank Distribution Chart Component
 * A compact SVG area chart showing game distribution across rankings (1-1000)
 * Pure vanilla JS implementation - no Alpine.js dependency
 */

(function() {
    'use strict';

    function RankDistributionChart(container, initialBins) {
        this.container = container;
        this.bins = initialBins || [];
        this.hoveredBin = null;

        this.svg = container.querySelector('.rank-distribution-svg');
        this.path = container.querySelector('.rank-distribution-fill');
        this.tooltip = container.querySelector('.rank-distribution-tooltip');
        this.rectsContainer = container.querySelector('.rank-distribution-rects');

        this.init();
    }

    RankDistributionChart.prototype.init = function() {
        var self = this;

        // Listen for updates
        window.addEventListener('rank-distribution-update', function(event) {
            if (Array.isArray(event.detail)) {
                self.bins = event.detail;
                self.render();
            }
        });

        // Initial render
        this.render();
    };

    RankDistributionChart.prototype.getMaxCount = function() {
        if (this.bins.length === 0) return 1;
        var counts = this.bins.map(function(b) { return b.count; });
        return Math.max.apply(null, counts) || 1;
    };

    RankDistributionChart.prototype.computePath = function() {
        if (this.bins.length === 0) return '';

        var width = 100;
        var height = 40;
        var binWidth = width / this.bins.length;
        var maxCount = this.getMaxCount();

        var points = this.bins.map(function(bin, i) {
            return {
                x: i * binWidth + binWidth / 2,
                y: height - (bin.count / maxCount) * (height - 6) - 2
            };
        });

        // Start path from bottom-left, up to first point
        var path = 'M0,' + height + ' L0,' + points[0].y + ' L' + points[0].x + ',' + points[0].y;

        // Use Catmull-Rom to Bezier conversion for smooth curve through all points
        if (points.length > 1) {
            for (var i = 0; i < points.length - 1; i++) {
                var p0 = points[i === 0 ? i : i - 1];
                var p1 = points[i];
                var p2 = points[i + 1];
                var p3 = points[i + 2 >= points.length ? i + 1 : i + 2];

                // Catmull-Rom to cubic bezier control points (tension = 0.5)
                var tension = 6;
                var cp1x = p1.x + (p2.x - p0.x) / tension;
                var cp1y = p1.y + (p2.y - p0.y) / tension;
                var cp2x = p2.x - (p3.x - p1.x) / tension;
                var cp2y = p2.y - (p3.y - p1.y) / tension;

                path += ' C' + cp1x + ',' + cp1y + ' ' + cp2x + ',' + cp2y + ' ' + p2.x + ',' + p2.y;
            }
        }

        // Close path to bottom-right and back
        path += ' L' + width + ',' + points[points.length - 1].y + ' L' + width + ',' + height + ' Z';
        return path;
    };

    RankDistributionChart.prototype.render = function() {
        var self = this;

        // Update visibility (use visibility instead of display to reserve space)
        if (this.bins.length === 0) {
            this.svg.style.visibility = 'hidden';
            return;
        }
        this.svg.style.visibility = 'visible';

        // Update path
        this.path.setAttribute('d', this.computePath());

        // Clear and recreate hover rects
        this.rectsContainer.innerHTML = '';
        var binWidth = 100 / this.bins.length;

        this.bins.forEach(function(bin, idx) {
            var rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
            rect.setAttribute('x', idx * binWidth);
            rect.setAttribute('y', 0);
            rect.setAttribute('width', binWidth);
            rect.setAttribute('height', 40);
            rect.setAttribute('fill', 'transparent');
            rect.style.cursor = 'help';

            rect.addEventListener('mouseenter', function(e) {
                self.showTooltip(idx, e);
            });
            rect.addEventListener('mouseleave', function() {
                self.hideTooltip();
            });

            self.rectsContainer.appendChild(rect);
        });
    };

    RankDistributionChart.prototype.showTooltip = function(binIndex, event) {
        this.hoveredBin = binIndex;
        var rect = event.currentTarget.getBoundingClientRect();
        var containerRect = this.container.getBoundingClientRect();
        var tooltipX = rect.left - containerRect.left + rect.width / 2;

        this.tooltip.style.left = tooltipX + 'px';
        this.tooltip.textContent = this.getTooltipText();
        this.tooltip.style.display = 'block';
    };

    RankDistributionChart.prototype.hideTooltip = function() {
        this.hoveredBin = null;
        this.tooltip.style.display = 'none';
    };

    RankDistributionChart.prototype.getTooltipText = function() {
        if (this.hoveredBin === null || !this.bins[this.hoveredBin]) return '';
        var bin = this.bins[this.hoveredBin];
        return bin.count + ' game' + (bin.count !== 1 ? 's' : '') + ' ranked ' + bin.binStart + '-' + bin.binEnd;
    };

    // Auto-initialize on DOM ready
    function initCharts() {
        var containers = document.querySelectorAll('.rank-distribution');
        containers.forEach(function(container) {
            if (container._rankDistributionChart) return; // Already initialized

            var dataAttr = container.getAttribute('data-bins');
            var initialBins = [];
            if (dataAttr) {
                try {
                    initialBins = JSON.parse(dataAttr);
                } catch (e) {
                    console.warn('Failed to parse rank distribution bins:', e);
                }
            }

            container._rankDistributionChart = new RankDistributionChart(container, initialBins);
        });
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initCharts);
    } else {
        initCharts();
    }

    // Also re-initialize after HTMX swaps
    document.addEventListener('htmx:afterSwap', function() {
        initCharts();
    });

    // Export for manual initialization if needed
    window.RankDistributionChart = RankDistributionChart;
})();
