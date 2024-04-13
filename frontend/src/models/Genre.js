import BaseModel from './BaseModel';

class Genre extends BaseModel {
    constructor(data) {
        super(data);
    }    

    toString() {
        return this.name;
    }
}

export default Genre;