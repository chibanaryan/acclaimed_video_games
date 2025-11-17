import BaseModel from './BaseModel';

/**
 * Represents a video game with metadata and IGDB integration
 * @extends BaseModel
 */
class Game extends BaseModel {
    /**
     * Create a new Game instance
     * @param {Object} data - The game data from the API
     */
    constructor(data) {
        super(data);
    }

    /**
     * Get the thumbnail URL for the game's cover art
     * @returns {string} IGDB thumbnail image URL
     */
    get thumbnail() {
        return `https://images.igdb.com/igdb/image/upload/t_cover_small/${this.igdbArtworkId}`;
    }

    /**
     * Get the full-size cover art URL
     * @returns {string} IGDB full-size image URL
     */
    get image() {
        return `https://images.igdb.com/igdb/image/upload/t_cover_big/${this.igdbArtworkId}`;
    }

    /**
     * Render the game description as HTML paragraphs
     * @returns {string} HTML string with description wrapped in <p> tags
     */
    get renderedDescription() {
        return this.description
            .split(/\r?\n/)
            .filter(x => x)
            .map(x => `<p>${x}</p>`)
            .join('');
    }

    /**
     * Get the decade the game was released (e.g., 1990, 2000, 2010)
     * @returns {number} The decade as a year (e.g., 1990 for games from 1990-1999)
     */
    get decade() {
        return parseInt(this.yearOfRelease / 10) * 10;
    }

    /**
     * Get a URL slug for the decade (e.g., "1990-99", "2000-09")
     * @returns {string} Decade slug in format "YYYY-YY" where YY is the last year's suffix
     */
    get decadeSlug() {
        let endYear = this.decade.toString().substring(2, 3);
        return `${this.decade}-${endYear}9`;
    }
}

export default Game;