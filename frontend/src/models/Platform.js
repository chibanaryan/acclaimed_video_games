import BaseModel from './BaseModel';

class Platform extends BaseModel {
    constructor(data) {
        super(data);
    }

    toString() {
        return this.name;
    }
}

export default Platform;