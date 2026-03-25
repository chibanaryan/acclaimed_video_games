/**
 * Rank Distribution Chart Component
 * A compact SVG area chart showing game distribution across rankings
 * Supports dynamic max rank via data-max-rank attribute
 * Pure vanilla JS implementation - no Alpine.js dependency
 */

(function() {
    'use strict';

    var DEFAULT_BIN_COUNT = 10;

    function isValidBinsArray(value) {
        if (!Array.isArray(value)) return false;
        for (var i = 0; i < value.length; i++) {
            var bin = value[i];
            if (!bin || typeof bin !== 'object') return false;
            if (typeof bin.binStart !== 'number' || typeof bin.binEnd !== 'number') return false;
            if (typeof bin.count !== 'number') return false;
        }
        return true;
    }

    function createZeroBins(maxRank, binCount) {
        if (!maxRank || maxRank <= 0) return [];
        var safeBinCount = binCount || DEFAULT_BIN_COUNT;
        var binSize = Math.ceil(maxRank / safeBinCount);
        var bins = [];
        for (var i = 0; i < safeBinCount; i++) {
            bins.push({
                binStart: i * binSize + 1,
                binEnd: Math.min((i + 1) * binSize, maxRank),
                count: 0,
            });
        }
        return bins;
    }

    function getMaxRankFromBins(bins) {
        if (!isValidBinsArray(bins) || bins.length === 0) return 0;
        var maxRank = 0;
        for (var i = 0; i < bins.length; i++) {
            maxRank = Math.max(maxRank, bins[i].binEnd || 0);
        }
        return maxRank;
    }

    function parseMaxRank(value) {
        if (typeof value === 'number') {
            return isNaN(value) ? 0 : Math.max(value, 0);
        }
        if (typeof value === 'string' && value.length > 0) {
            var parsed = parseInt(value, 10);
            return isNaN(parsed) ? 0 : Math.max(parsed, 0);
        }
        return 0;
    }

    function resolveMaxRank(explicitMaxRank, bins) {
        var parsedMaxRank = parseMaxRank(explicitMaxRank);
        if (parsedMaxRank > 0) {
            return parsedMaxRank;
        }
        return getMaxRankFromBins(bins);
    }

    function parseBinsFromDataAttribute(container) {
        if (!container) return [];
        var dataAttr = container.getAttribute('data-bins');
        if (!dataAttr) return [];
        try {
            var parsed = JSON.parse(dataAttr);
            return isValidBinsArray(parsed) ? parsed : [];
        } catch (e) {
            return [];
        }
    }

    function normalizeBins(rawBins, chart) {
        if (isValidBinsArray(rawBins) && rawBins.length > 0) {
            return rawBins;
        }

        var domBins = parseBinsFromDataAttribute(chart.container);
        if (domBins.length > 0) {
            return domBins;
        }

        if (Array.isArray(chart.bins) && chart.bins.length > 0) {
            return chart.bins;
        }

        return createZeroBins(chart.maxRank, chart.binCount || DEFAULT_BIN_COUNT);
    }

    function RankDistributionChart(container, initialBins, maxRank) {
        this.container = container;
        this.hasExplicitMaxRank = parseMaxRank(maxRank) > 0;
        this.maxRank = resolveMaxRank(maxRank, initialBins);
        this.binCount =
            Array.isArray(initialBins) && initialBins.length > 0
                ? initialBins.length
                : DEFAULT_BIN_COUNT;
        this.bins = isValidBinsArray(initialBins)
            ? initialBins
            : createZeroBins(this.maxRank, this.binCount);
        if (!this.maxRank) {
            this.maxRank = resolveMaxRank(maxRank, this.bins);
        }
        this.hoveredBin = null;

        this.svg = container.querySelector('.rank-distribution-svg');
        this.path = container.querySelector('.rank-distribution-fill');
        this.tooltip = container.querySelector('.rank-distribution-tooltip');
        this.rectsContainer = container.querySelector('.rank-distribution-rects');
        // Peak indicator is in the parent section's header
        var section = container.closest('.rank-distribution-section');
        this.peakLabel = section ? section.querySelector('.rank-distribution-peak') : null;

        // X-axis labels
        var axis = container.querySelector('.rank-distribution-axis');
        this.axisMin = axis ? axis.querySelector('.rank-axis-min') : null;
        this.axisMid = axis ? axis.querySelector('.rank-axis-mid') : null;
        this.axisMax = axis ? axis.querySelector('.rank-axis-max') : null;

        this.init();
    }

    RankDistributionChart.prototype.init = function() {
        var self = this;

        // Note: Updates are handled by a single global listener (setupGlobalListener)
        // to prevent memory leaks from per-instance listeners accumulating

        // Event delegation for hover rects (single listener instead of per-rect)
        this.rectsContainer.addEventListener('mouseenter', function(e) {
            if (e.target.tagName === 'rect' && e.target.dataset.binIndex !== undefined) {
                self.showTooltip(parseInt(e.target.dataset.binIndex, 10), e);
            }
        }, true);
        this.rectsContainer.addEventListener('mouseleave', function(e) {
            if (e.target.tagName === 'rect') {
                self.hideTooltip();
            }
        }, true);

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
        var maxCount = this.getMaxCount();
        var numBins = this.bins.length;

        // Position points at edges: first at x=0, last at x=width
        // This eliminates flat sections at start/end of the chart
        var points = this.bins.map(function(bin, i) {
            var x = numBins === 1 ? width / 2 : (i / (numBins - 1)) * width;
            return {
                x: x,
                y: height - (bin.count / maxCount) * (height - 6) - 2
            };
        });

        // Start path from bottom-left, up to first point (which is now at x=0)
        var path = 'M0,' + height + ' L' + points[0].x + ',' + points[0].y;

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

        // Close path to bottom-right (last point is now at x=width) and back
        path += ' L' + width + ',' + height + ' Z';
        return path;
    };

    RankDistributionChart.prototype.render = function() {
        var self = this;

        // Update visibility (use visibility instead of display to reserve space)
        if (this.bins.length === 0) {
            this.svg.style.visibility = 'hidden';
            if (this.peakLabel) this.peakLabel.textContent = '';
            return;
        }
        this.svg.style.visibility = 'visible';

        // Update x-axis labels based on maxRank
        if (this.axisMin) this.axisMin.textContent = '1';
        if (this.axisMid) this.axisMid.textContent = Math.ceil(this.maxRank / 2);
        if (this.axisMax) this.axisMax.textContent = this.maxRank;

        // Update peak indicator
        var maxCount = this.getMaxCount();
        if (this.peakLabel) {
            this.peakLabel.textContent = 'Peak: ' + maxCount;
        }

        // Update path
        this.path.setAttribute('d', this.computePath());

        // Clear and recreate hover rects using DocumentFragment (single reflow)
        this.rectsContainer.innerHTML = '';
        var binWidth = 100 / this.bins.length;
        var fragment = document.createDocumentFragment();

        this.bins.forEach(function(bin, idx) {
            var rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
            rect.setAttribute('x', idx * binWidth);
            rect.setAttribute('y', 0);
            rect.setAttribute('width', binWidth);
            rect.setAttribute('height', 40);
            rect.setAttribute('fill', 'transparent');
            rect.style.cursor = 'help';
            rect.dataset.binIndex = idx;
            fragment.appendChild(rect);
        });

        // Single DOM insertion triggers only one reflow
        this.rectsContainer.appendChild(fragment);
    };

    RankDistributionChart.prototype.showTooltip = function(binIndex, event) {
        this.hoveredBin = binIndex;
        var rect = event.target.getBoundingClientRect();
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

    // Cleanup method for memory leak prevention
    RankDistributionChart.prototype.destroy = function() {
        // No per-instance listeners to clean up - global listener handles updates
        // This method is called when chart container is removed from DOM
    };

    // Track all active charts for global event handling (memory leak fix)
    var activeCharts = [];
    var globalListenerInitialized = false;

    function setupGlobalListener() {
        if (globalListenerInitialized) return;
        globalListenerInitialized = true;

        window.addEventListener('rank-distribution-update', function(event) {
            // Update all charts that are still in the DOM
            activeCharts = activeCharts.filter(function(chart) {
                if (document.contains(chart.container)) {
                    var incomingBins = event.detail;
                    if (
                        incomingBins &&
                        typeof incomingBins === 'object' &&
                        !Array.isArray(incomingBins) &&
                        Array.isArray(incomingBins.bins)
                    ) {
                        incomingBins = incomingBins.bins;
                    }
                    var nextBins = normalizeBins(incomingBins, chart);
                    chart.bins = nextBins;
                    if (Array.isArray(nextBins) && nextBins.length > 0) {
                        chart.binCount = nextBins.length;
                    }
                    if (!chart.hasExplicitMaxRank) {
                        chart.maxRank = resolveMaxRank(null, nextBins);
                    }
                    chart.render();
                    return true;
                }
                // Chart container removed from DOM, clean up
                chart.destroy();
                return false;
            });
        });
    }

    // Auto-initialize on DOM ready
    function initCharts() {
        pruneStaleCharts();

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

            // Prefer the explicit server max rank; otherwise infer it from bins.
            var maxRankAttr = container.getAttribute('data-max-rank');
            var maxRank = parseMaxRank(maxRankAttr);

            if (!isValidBinsArray(initialBins)) {
                initialBins = createZeroBins(maxRank, DEFAULT_BIN_COUNT);
            } else if (maxRank === 0) {
                maxRank = getMaxRankFromBins(initialBins);
            }

            var chart = new RankDistributionChart(container, initialBins, maxRank);
            container._rankDistributionChart = chart;
            activeCharts.push(chart);
        });

        setupGlobalListener();
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initCharts);
    } else {
        initCharts();
    }

    // Prune charts whose containers are no longer in the DOM
    function pruneStaleCharts() {
        activeCharts = activeCharts.filter(function(chart) {
            if (document.contains(chart.container)) {
                return true;
            }
            chart.destroy();
            return false;
        });
    }

    // Also re-initialize after HTMX swaps
    document.addEventListener('htmx:afterSwap', function() {
        pruneStaleCharts();
        initCharts();
    });

    // Manual DOM swaps (non-HTMX) can replace chart containers.
    // Allow other modules to request (re)initialization explicitly.
    window.addEventListener('rank-distribution-init', function() {
        initCharts();
    });

    // Re-render charts after bfcache restoration
    // The bfcache preserves chart.bins from before navigation, so render() restores
    // the visual state immediately. The filter component's bfcache-restore handler
    // then dispatches rank-distribution-update with fresh data to correct any staleness.
    window.addEventListener('bfcache-restore', function() {
        activeCharts = activeCharts.filter(function(chart) {
            if (document.contains(chart.container)) {
                chart.render();
                return true;
            }
            chart.destroy();
            return false;
        });
    });

    // Export for manual initialization if needed
    window.RankDistributionChart = RankDistributionChart;
    window.initRankDistributionCharts = initCharts;
})();
