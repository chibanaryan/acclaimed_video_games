import BaseModel from './BaseModel';

class Game extends BaseModel {
    constructor(data) {
        super(data);
    }

    get thumbnail() {
        return `https://images.igdb.com/igdb/image/upload/t_cover_small/${this.igdbArtworkId}`;
    }

    get image() {
        return `https://images.igdb.com/igdb/image/upload/t_cover_big/${this.igdbArtworkId}`;
    }

    get renderedDescription() {
        return this.description
            .split(/\r?\n/)
            .filter(x => x)
            .map(x => `<p>${x}</p>`)
            .join('');
    }

    get decade() {
        return parseInt(this.yearOfRelease / 10) * 10;
    }

    get decadeSlug() {
        let endYear = this.decade.toString().substring(2, 3);
        return `${this.decade}-${endYear}9`;
    }
}

export default Game;