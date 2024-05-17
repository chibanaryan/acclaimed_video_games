<template>
    <nav class="navbar"
        role="navigation"
        aria-label="main navigation">
        <div class="navbar-brand">
            <router-link :to="{ name: 'home' }"
                class="navbar-item has-text-weight-bold pl-0">
                <img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAZEAAAEHCAYAAABvHnsJAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAAJcEhZcwAAFiQAABYkAZsVxhQAAAlnSURBVHhe7d1/iB90Hcfxz3e33XlzOp3bzLkf6jRX2ApS1OWw1MwKHQzaQPpHCsSFxfrH/RFU/mEagrA/HFIGMioi+isiUibo8DRshDpsLjXXfvlj7tjv+/1ti09/JCK71913u/ve4wFfdq/vH/fXd/fc7rbvu9FsNgsAJKbVXwFg1EQEgJiIABATEQBiIgJATEQAiIkIADERASAmIgDERASAmIgAEBMRAGIiAkBMRACIiQgAMREBICYiAMREBICY87hw0po1a5p33HFHXbm+vr6ybt26Rp3Q9kQETnrsscea69evryt3+PDh8tBDD5WHH35YSJgSfDsLgJiIABATEQBiIgJATEQAiIkIADERASAmIgDERASAmIgAEBMRAGIiAkBMRACIiQgAMREBICYiAMREBICYiAAQExEAYiICQExEAIiJCAAxEQEgJiIAxEQEgJiIABATEQBiIgJATEQAiIkIADERASAmIgDERASAmIgAEBMROGnx4sX1o7GbP39+/QjaX6PZbNYP+Z/nnnuuefPNN9cF8MmefvrpcvvttzfqnFL8TQSAmIgAEBMRAGIiAkBMRACIiQgAMREBICYiAMREBICYiAAQExEAYiICQExEAIiJCAAxEQEgJiIAxNrqKNW6deuaS5YsqStzwTm95er5b5XGlDwvA2QaZeeBq8rBY+fXndu7d2/ZuHHjpPkK1FYR2bJlS3PFihV1Zd599edl/sAv6wI4Pb2z7i8XLbu/rty2bdvKTTfdNGki0lbfzurs7Czd3d1jekzrmFE/G8Dp6zj5tePjvqaM9tHV1VU/4+TgZyIAxEQEgJiIABATEQBiIgJATEQ+ouE/iACcNhEBICYiAMREBICYiAAQExEAYiICQExEAIiJCACxtron8vwzm5vXXNZXV+bI+9vK3JE/1QVweno7V5eZc66pK/fG3vPLjV9e6yjV6XrwwQebixYtqis3a8aBctk5T5fPXryjPgMw+bz+3rLyTt/t5ejg3PpMZseOHeWRRx5peYzOekR6enrGfI3wlKEP/lj6d6yrC2DyOj53Q5n3me/Vldm0aVO57777Wh4RPxMBICYiAMREBICYiAAQExEAYiICQExEAIiJCAAxEQEgJiIAxEQEgJiIABATEQBiIgJATEQAiIkIADERASDmsuEksG/wljJQ5tQ1eh1D+8qi7p664OzbP3RL6W/mr+lT+g/tKFfP3V5Xe5lMlw1FZIJ758i1ZdlXHi8d3ZfUZ0av980nS+f+n9QFZ1/XssfL9Hl31pV5/ndryxcXtOcfjpzHZdwcH76wNLourgtgYhERAGIiAkBMRACIiQgAMREBICYiAMREBICYiAAQExEAYiICQExEAIiJCAAxEQEgJiIAxERkguueeX5pNFp+EgDOqP73nynHdv92TI/uzoH62TibHKVqoRlX/LQ0ZlxUV6Zj9vVlWten6sqM9L9bhg/9ta6xOfrh66XzwON1MaUsfKB0nruojtwHbzxZZpe/15V758Qt5dNfWF1X5njvzjL9/Y11TRwuG45CO0dkPK63TTQH//mL0vXug3UxlTQuf7TMXLi2rtzOrRvKpeXXdeXePH5n+fzXxvYHmkP/eqpM3/OjuiYOlw0BmBJEBICYiAAQExEAYiICQExEAIiJCAAxEQEgJiIAxEQEgJiIABATEQBiIgJATEQAiIkIADH3RFpo//CtZaA5tqNUMy9dXZZctWJM1w0Hju0u+/+xuRw78mF9JtcxtLcsPOeFuphK9g1+pQw25tWVmzn8SpnX9UZdud0DXy0j0y6sKzN9ZH+5tHNrXROHo1Sj0M4RGQ87j37zv4d3pk3L/9I4UQ/vMHUNn//1MjLr+royb2//c7l6zvhc7JxoHKVi3AwNjf2O9MjwUP0IJoaZC+4sFyz9zpgeR/s66mfjbBIRAGIiAkBMRACIiQgAMREBICYiAMREBICYiAAQExEAYiICQExEAIiJCAAxEQEgJiIAxERkguuedrD0HdlV+vv748d4vJ08jKehwb4yMDAQP/pP/p6Y1Xm4fjbOJkepJoF3jl5bTgzNqWv0ZjTfK1de+Epd7Wfnh58rx4cuqKs9nNt5qFx14at1tZ9/H7+hnBjOX9PdHQfL4pkv1dV+XDYcBRFhrBqXP1pmLlxbV3vwep7aXDYEYEoQEQBiIgJATEQAiIkIADERASAmIgDERASAmIgAEBMRAGIiAkBMRACIiQgAMREBICYiAMREBICYiDDpnTqsNjIy0nYPmAxcNmTS23Xs+tI3clFd7aHdz7/yyZzHHQURAfh/zuMCMCWICAAxEQEgJiIAxEQEgJiIABATEQBiIgJATEQAiIkIADERASAmIgDERASAmIgAEBMRAGIiAkDsrB+lGi/Hti5a8daJu164aP5l9ZnMid7t5ZLpz9ZFKx059+4yPG1uXbTC8YPby4IZXs9nwgeNb5QZs66sK9f74d5yeecfvnTuyt099akJrW0icsrWrVubK1eurCuz628PlbknNtVFK40s/lk5b8m366IV3n7px+XiwV/VRSsdnv3Dcsny9XXlXn755XLddde1/CLhePHtLABiIgJATEQAiIkIADERASAmIgDEROQjGo1J8y/rAM46EQEgJiIAxEQEgJiIABATEQBiIgJATEQAiIkIALG2uieyadOm5vLly+vKzO77/amDMHXRSnuad5cDHXfVRSt4PZ85u4bWlN7O1XXldu7cWe65555J87+e2yoi4+H7965q3rv2inLe7Pn1GVphZGS4zOt7YtJcb5usHvjBmuZ3v3Vl6eo+rz5DKxw8sLts+s1b5Ymn/jLl3vJCRD7Giy++2LzxxhvrohUGBgZKZ2en95g5A/bt29dcsGBBXbTCli1byq233jolX89+JgJATEQAiIkIADERASAmIgDERASAmIgAEBMRAGIiAkBMRACIiQgAMREBICYiAMREBICYt4L/GD09Pc0bbrihLlphcHCwdHV1eSv4M2DPnj3eCr7Fnn322XLbbbdNydeziHyMjRs3NpcuXVoXrTA0NFRWrVolImfA5s2bm3PmzKmLVnjttdfKhg0bRAQARsPPRACIiQgAMREBICYiAMREBICYiAAQExEAYiICQExEAIiJCAAxEQEgJiIAxEQEgJiIABATEQBiIgJATEQAiIkIADERASAmIgDERASAmIgAEBMRAGIiAkBMRACIiQgAoVL+A7S0hp1dmSkdAAAAAElFTkSuQmCC"
                    alt="" />
            </router-link>
            <router-link :to="{ name: 'games-list', params: { slug: 'alltime' } }"
                class="navbar-item">
                Top 1000
            </router-link>
            <game-search-component class="is-hidden-tablet navbar-item is-expanded"></game-search-component>
            <a @click="expanded = !expanded"
                class="navbar-burger"
                :class="{ 'is-active': expanded }"
                aria-label="menu"
                aria-expanded="false"
                role="button">
                <span aria-hidden="true"></span>
                <span aria-hidden="true"></span>
                <span aria-hidden="true"></span>
                <span aria-hidden="true"></span>
            </a>
        </div>
        <div class="navbar-menu"
            :class="{ 'is-active': expanded }">
            <div class="navbar-start">
                <router-link :to="{ name: 'developers-list' }"
                    class="navbar-item">
                    Developers
                </router-link>
                <router-link :to="{ name: 'list-list' }"
                    class="navbar-item">
                    Lists
                </router-link>
                <router-link :to="{ name: 'page-detail', params: { slug: 'about' } }"
                    class="navbar-item">
                    About
                </router-link>
                <router-link :to="{ name: 'page-detail', params: { slug: 'palestine' } }"
                    class="navbar-item"
                    title="Statement on Palestine">
                    <span class="icon">
                        <img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAPoAAAB9CAIAAAAEO+kKAAAAGXRFWHRTb2Z0d2FyZQBBZG9iZSBJbWFnZVJlYWR5ccllPAAAAyZpVFh0WE1MOmNvbS5hZG9iZS54bXAAAAAAADw/eHBhY2tldCBiZWdpbj0i77u/IiBpZD0iVzVNME1wQ2VoaUh6cmVTek5UY3prYzlkIj8+IDx4OnhtcG1ldGEgeG1sbnM6eD0iYWRvYmU6bnM6bWV0YS8iIHg6eG1wdGs9IkFkb2JlIFhNUCBDb3JlIDUuNi1jMTExIDc5LjE1ODMyNSwgMjAxNS8wOS8xMC0wMToxMDoyMCAgICAgICAgIj4gPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4gPHJkZjpEZXNjcmlwdGlvbiByZGY6YWJvdXQ9IiIgeG1sbnM6eG1wPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvIiB4bWxuczp4bXBNTT0iaHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wL21tLyIgeG1sbnM6c3RSZWY9Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC9zVHlwZS9SZXNvdXJjZVJlZiMiIHhtcDpDcmVhdG9yVG9vbD0iQWRvYmUgUGhvdG9zaG9wIENDIDIwMTUgKFdpbmRvd3MpIiB4bXBNTTpJbnN0YW5jZUlEPSJ4bXAuaWlkOjRCNDA4OUY1MEQwNzExRTY4QUEwQUQ2QTgyQTg0OENFIiB4bXBNTTpEb2N1bWVudElEPSJ4bXAuZGlkOjRCNDA4OUY2MEQwNzExRTY4QUEwQUQ2QTgyQTg0OENFIj4gPHhtcE1NOkRlcml2ZWRGcm9tIHN0UmVmOmluc3RhbmNlSUQ9InhtcC5paWQ6NEI0MDg5RjMwRDA3MTFFNjhBQTBBRDZBODJBODQ4Q0UiIHN0UmVmOmRvY3VtZW50SUQ9InhtcC5kaWQ6NEI0MDg5RjQwRDA3MTFFNjhBQTBBRDZBODJBODQ4Q0UiLz4gPC9yZGY6RGVzY3JpcHRpb24+IDwvcmRmOlJERj4gPC94OnhtcG1ldGE+IDw/eHBhY2tldCBlbmQ9InIiPz59TjhxAAAECUlEQVR42uydy0uUYRxG3+8yOeOMM9mYGDEaLTIMki4L23WTLos2YVHgIoRaVIuWQZARREouIjIiiJCIdgUt/BMCLd1EmYswWkVB3sZpLn5vY240WkULeZ9zNuLu4/sdHs5sZkx/clPaCwyAApMbtr9Mb9kZJHgV4Dz+vI1aw/jjdO5MTT2vA9wmuJDIVoyNGa9zXWqzHxupFIrG8l7AzXVf/lM1Pm+jkzWZobocYQOO616lOulzhA04HzMr/ydsQGLdVxpP2ICK7oQNqMQMYQNy607YgKLuhA2oxAxhA3LrTtiAou6EDajEDGEDcutO2ICi7oQNqMQMYQNy607YgKLuhA2oxAxhA3LrTtiAou6EDajEDGEDcutO2ICi7oQNqMQMYQNy607YgKLuhA2oxAxhA3LrTtiAou6EDajEDGEDcutO2ICi7oQNqMQMYQNy607YgKLuhA2oxAxhA3Lr/tewaQ8JG/g/eGP129by8yU8f7ZcGkqa/IlDvjW2UuFm8M+Ea/z5CjaKB8Hlop9NNDXc6TWhz83AtZhZyaLnLdho6t6j9x1H86Pj3Axc1v13c3lBJl14NzF57Oy3h0OcDZzWfflZaxO2VPp86epUz5XFHzMcD1zWfWnlwzBIJb8/ef6xsys/QtiA07qvCpvjhA04rzthA2q6EzagpTthA2K6EzagpjthA1q6EzYgpjthA2q6EzagpTthA2K6EzagpjthA1q6EzYgpjthA2q6rw6bU/Ov3xjLFxygu/Nhsz6Tfzv26fT54tQXzo/uTmPt4vRMclf71mcPalpynF+NUEj1SiVa+Jnt7soN3AizfEUZurtLtFDwk7XNd681XjzH1dHd6YCZnatt39F8/3Zq315Oju4EDKA7AQPoTsAAuhMwgO4EDKA7AQPoTsAAuhMwgO4EDKjoTsCAiu4EDGjoTsCAiO4EDKjoTsCAhu7WRLNzifa2lsG+ZMcezgbO6h5EtqYc1fd0Nw70mjp+QRvc1T1RtvOhHTzS9LUz7g/32TK/mg0u6u4ZkypGHzbGrh/OjOcCMzpsooiDgYO6h5GJV+yLttpb+9PTKd+UrInFuRY4qHs1YBZiXv+B9NPdyeqH1CXXAdzTfVXANK9bEh3VwUnd/wyYIqaDo7oTMCChOwEDKroTMKCiOwEDEroTMKCiOwEDKroTMCChOwEDKroTMKCiOwEDEroTMKCiOwEDKroTMCChOwEDKroTMKCiOwEDEroTMKCiOwEDKroTMCChOwEDKroTMKCiOwEDEroTMKCiOwEDKroTMCChOwEDKroTMKCiOwEDEroTMKCiOwEDKroTMCChOwEDKroTMKCiOwEDKrqnSnaiISRgQEL3V63xmwczBAwo8EuAAQBLfm7n+J90owAAAABJRU5ErkJggjE5NDU="
                            alt="" />
                    </span>
                    <span class="is-hidden-tablet">Statement on Palestine</span>
                </router-link>
                <game-search-component class="is-hidden-mobile navbar-item is-expanded"></game-search-component>
            </div>
        </div>
    </nav>
</template>

<script>
import GameSearchComponent from "./GameSearchComponent";

export default {
    components: {
        GameSearchComponent,
    },
    data() {
        return {
            expanded: false,
        }
    }
}
</script>

<style>
header .container .navbar .navbar-menu {
    background-color: #131313
}
</style>