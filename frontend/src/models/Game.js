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
}

export default Game;