let sc_courses, sc_name, sc_prerequisites, sc_type, sc_subbranches;
switch(naming) {
    case 'compact':
        sc_courses = 'c';
        sc_name = 'n';
        sc_prerequisites = 'p';
        sc_type = 't';
        sc_subbranches = 's';
        break;
    default:
        sc_courses = 'courses';
        sc_name = 'name';
        sc_prerequisites = 'prerequisites';
        sc_type = 'type';
        sc_subbranches = 'sub-branches';
        break;
}

// Strip/trim whitespace etc
// https://stackoverflow.com/questions/1418050/string-strip-for-javascript
if (typeof(String.prototype.trim) === "undefined") {
    String.prototype.trim = function() {
        return String(this).replace(/^\s+|\s+$/g, '');
    };
}

// Hash function from Java
// Collisions relatively unlikely: https://stackoverflow.com/questions/9406775/why-does-string-hashcode-in-java-have-many-conflicts
// https://werxltd.com/wp/2010/05/13/javascript-implementation-of-javas-string-hashcode-method/
String.prototype.hashCode = function(){
    var hash = 0;
    if (this.length == 0) return hash;
    for (i = 0; i < this.length; i++) {
        char = this.charCodeAt(i);
        hash = ((hash<<5)-hash)+char;
        hash = hash & hash; // Convert to 32bit integer
    }
    return hash;
}

class LogicalBranch {
    constructor(node_type, courses, subbranches) {
        this.node_type = node_type;
        this.courses = courses;
        this.subbranches = subbranches;
    }

    toString(hash_subbranch) {
        let subbranch_str = hash_subbranch ? JSON.stringify(this.subbranches).hashCode().toString() : 
                                             JSON.stringify(this.subbranches);

        let hash = '[' + this.node_type + ']_[' + 
                         this.courses.toString() + ']_[' + 
                         subbranch_str + 
                   ']';
        return hash
    }
}

class Edge {
    constructor(from, to) {
        // from and to are node indices
        this.from = from;
        this.to = to;
    }

    toString() {
        return this.from.toString() + '-' + this.to.toString();
    }
}

window.onload = function visualize(){
    var hash_subbranches = true;

    var node_list = [];
    var edge_list = [];
    var course_table = {};  // hash that prevents duplicate courses
    var branch_table = {};  // hash that prevents duplicates for AND/OR nodes
    var edge_table = {};    // hash that prevents duplicate edges
    var or_counter = 0, and_counter = 0, node_counter = -1;

    function create_root(course_info, key_node){
        let node_id = ++node_counter;
        course_name = course_info[sc_name];

        if (course_name in course_table) {
            node_id = course_table[course_name];
        } else {
            color = key_node ? 'rgb(255,182,193)' : 'rgb(151,194,252)';
            node_list.push({id: node_id, label: course_name, color: color});
            course_table[course_name] = node_id
        }

        if (sc_prerequisites in course_info){
            prerequisites = course_info[sc_prerequisites];
            create_branch(prerequisites, node_id);
        }
    }

    function create_branch(branch, parent_id){
        if (typeof branch === 'object') {
            let node_id = ++node_counter;
            let node_type = branch[sc_type];
            let node_name;

            switch (node_type) {
                case 'AND': and_counter++; node_name = 'AND' + and_counter.toString(); break;
                case 'OR':  or_counter++; node_name = 'OR' + or_counter.toString(); break;
                default: node_name = 'UNKNOWN:'; return; 
                // default possibilities: 
                // -  empty prerequisites dict. In this case, 
                //    just return and do not add any node.
                //    note that, one of the node counter values was still
                //    reserved for this un-created node in this case.
                // -  UPDATED: This should be resolved in generating js now.
                //    leave here just as a safety measure.
            }

            hash_node_name = node_name.includes('AND') ? 'AND' : 'OR';
            hash_courses = typeof branch[sc_courses] === 'undefined' ? '{1}' : branch[sc_courses];
            hash_subbranches = typeof branch[sc_subbranches] === 'undefined' ? '{2}' : branch[sc_subbranches];
            branch_hash = new LogicalBranch(hash_node_name, hash_courses, hash_subbranches);
            // console.log(branch_hash.toString(true));

            if (!(branch_hash.toString(hash_subbranches) in branch_table)) {
                branch_table[branch_hash.toString(hash_subbranches)] = node_id;
                node_list.push({id: node_id, label: node_name});

                edge_hash = new Edge(parent_id, node_id);
                if (!(edge_hash.toString() in edge_table)) {
                    edge_list.push({from: parent_id, to: node_id, arrows:'to'});
                    edge_table[edge_hash.toString()] = 1;
                    // console.log(edge_hash.toString());
                } else {
                    return;
                }
                
            } else {
                node_id = branch_table[branch_hash.toString(hash_subbranches)];

                edge_hash = new Edge(parent_id, node_id);
                if (!(edge_hash.toString() in edge_table)) {
                    edge_list.push({from: parent_id, to: node_id, arrows:'to'});
                    edge_table[edge_hash.toString()] = 1;
                    // console.log(edge_hash.toString());
                }
                return; // some node id's unused
            }

            
            if (sc_courses in branch) {
                for (course of branch[sc_courses]) {
                    create_branch(course, node_id);
                }
            }
            if (sc_subbranches in branch) {
                for (subbranch of branch[sc_subbranches]) {
                    create_branch(subbranch, node_id);
                }
            }
        } else if (typeof branch === 'string') {
            let course_name = branch; // course
            let node_id;

            if (!(course_name in course_table)) {
                node_id = ++node_counter;
                course_table[course_name] = node_id;
                node_list.push({id: node_id, label: course_name});
                
                if (course_name in master_course_graph) {
                    create_root(master_course_graph[course_name], false);
                }
            } else {
                node_id = course_table[course_name];
            }

            edge_list.push({from: parent_id, to: node_id, arrows:'to'});
            
        }
        
    }

    var course_graph = document.getElementById('courseGraph'),
        course_input = document.getElementById('courseInput'),
        course_reset = document.getElementById('btnReset');
    
    // https://stackoverflow.com/questions/26946235/pure-javascript-listen-to-input-value-change
    course_input.addEventListener('input', update);
    course_reset.addEventListener('mousedown', reset);

    // create a network
    var container = course_graph;
    var options = {
        autoResize: true,
        height: '100%',
        width: '100%'
    };

    var nodes = new vis.DataSet(node_list);
    var edges = new vis.DataSet(edge_list);
    var data = {
        nodes: nodes,
        edges: edges
    };
    var network = new vis.Network(container, data, options);
    
    function update() {
        let course_list = course_input.value.split(',');

        // inefficient to redefine network each time!
        for (course_name of course_list) {
            course_name = course_name.trim().toUpperCase();
            let tokens = course_name.split(' ');

            // Elec Eng XXXX -> Eleceng XXXX
            // regex source: https://stackoverflow.com/questions/23476532/check-if-string-contains-only-letters-in-javascript
            if (tokens.length > 1 && /^[a-zA-Z]+$/.test(tokens[0]) && /^[a-zA-Z]+$/.test(tokens[1])) {
                tokens = [tokens[0] + tokens[1]].concat(tokens.slice(2));
                course_name = tokens.join(' ');
            }

            if (!(course_name in master_course_graph) || (course_name in course_table)) continue;
    
            let course_info = master_course_graph[course_name];
            create_root(course_info, true);
    
            // console.log(course_table);
            
            // create a network
            container = course_graph;
    
            nodes = new vis.DataSet(node_list);
            edges = new vis.DataSet(edge_list);
            data = {
                nodes: nodes,
                edges: edges
            };
            network = new vis.Network(container, data, options);
        }
        
    }

    function reset() {
        course_table = {};  
        branch_table = {};  
        edge_table = {};    
        or_counter = 0, and_counter = 0, node_counter = -1;
        node_list = [];
        edge_list = [];

        nodes = new vis.DataSet(node_list);
        edges = new vis.DataSet(edge_list);
        data = {
            nodes: nodes,
            edges: edges
        };
        network = new vis.Network(container, data, options);
        network.redraw();

        // console.log(course_table);
    }


}
