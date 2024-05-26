import { LIST_TYPE_LABELS } from "../constants";
import BaseModel from './BaseModel';

class List extends BaseModel {
    get typeName() {
        return LIST_TYPE_LABELS[this.type] || this.type;
    }
}

export default List;