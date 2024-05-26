import BaseModel from './BaseModel';
import Developer from './Developer';

class DeveloperAlias extends BaseModel {
    constructor(data) {
        super(data);
        this.developer = new Developer(this.developer);
    }

    toString() {
        return `${this.name} (${this.developer.name})`;
    }
}

export default DeveloperAlias;