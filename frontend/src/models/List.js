import { LIST_TYPE_LABELS } from "../constants";
import BaseModel from './BaseModel';

class List extends BaseModel {
    // constructor(data) {
    //     Object.assign(this, data);
    // }

    get typeName() {
        return LIST_TYPE_LABELS[this.type] || this.type;
    }
}

export default List;