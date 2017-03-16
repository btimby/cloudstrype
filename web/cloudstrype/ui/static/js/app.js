var app = app || {};

(function($) {

/*==============================================================
            ___  ___          _      _     
            |  \/  |         | |    | |    
            | .  . | ___   __| | ___| |___ 
            | |\/| |/ _ \ / _` |/ _ \ / __|
            | |  | | (_) | (_| |  __/ \__ \
            \_|  |_/\___/ \__,_|\___|_|___/
                                           
================================================================*/

/*-------------------------------------------------------------
                        UserModel
-------------------------------------------------------------*/

    app.UserModel = Backbone.Model.extend({
        /* Model for user information. */
        url: '/api/v1/me/',
    });

/*-------------------------------------------------------------
                        DirectoryModel
-------------------------------------------------------------*/

    app.DirectoryModel = Backbone.Model.extend({
        /* Model that represents a single directory */

        idAddtribute: 'uid',

        url: function() {
            return '/api/v1/me/dirs/path:/' + this.path + ':';
        },

        defaults: {
            isDirectory: true,
            tags: [],
            attrs: {}
        },

        initialize: function() {
            Backbone.Select.Me.applyTo(this);
        }
    });

/*-------------------------------------------------------------
                        FileModel
-------------------------------------------------------------*/

    app.FileModel = Backbone.Model.extend({
        /* Model that represents a single file. */

        idAddtribute: 'uid',

        url: function() {
            return '/api/v1/me/files/path:/' + this.path + ':';
        },

        defaults: {
            isDirectory: false,
            tags: [],
            attrs: {}
        },

        initialize: function() {
            Backbone.Select.Me.applyTo(this);
        }
    });

/*==============================================================
          _____       _ _           _   _                 
        /  __ \     | | |         | | (_)                
        | /  \/ ___ | | | ___  ___| |_ _  ___  _ __  ___ 
        | |    / _ \| | |/ _ \/ __| __| |/ _ \| '_ \/ __|
        | \__/\ (_) | | |  __/ (__| |_| | (_) | | | \__ \
         \____/\___/|_|_|\___|\___|\__|_|\___/|_| |_|___/
                                                         
================================================================*/

/*-------------------------------------------------------------
                        PathCollection
-------------------------------------------------------------*/

    app.PathCollection = Backbone.Collection.extend({
        model: function(attrs, options) {
            if (attrs.mime == 'application/x-directory') {
                return new app.DirectoryModel(attrs, options);
            } else {
                return new app.FileModel(attrs, options);
            }
        },

        url: function() {
            // TODO: use current directory.
            return '/api/v1/me/dirs/path:/:';
        },

        initialize: function(models, options) {
            Backbone.Select.Many.applyTo(this, models, options);
        }
    });

 /*==============================================================
            _   _ _                   
            | | | (_)                  
            | | | |_  _____      _____ 
            | | | | |/ _ \ \ /\ / / __|
            \ \_/ / |  __/\ V  V /\__ \
             \___/|_|\___| \_/\_/ |___/
                                       
================================================================*/

/*-------------------------------------------------------------
                        AppView
-------------------------------------------------------------*/

    app.AppView = Backbone.View.extend({
        /* View to orchestrate the entire application. */

        //el: '#main-el',

        initialize: function() {
            this.userView = new app.UserView();
            this.pathListView = new app.PathListView();
            this.pathMenuView = new app.PathMenuView({
                collection: this.pathListView.selected
            });
            this.breadCrumbView = new app.BreadCrumbView();
        },

        render: function() {
            // As of now, nothing to render.
        },

        files: function(path) {
            /* Called when the user navigate to /files*path. We do the ajax
            here because we need to initialize a model for the directory itself
            as well as a collection for all the directories and files it
            contains. All of which is returned in the same call. */
            $.get('/api/v1/me/dirs/path:' + path + ':', function(data) {
                this.breadCrumbView.model.set(data.info);
                this.pathListView.collection.add(data.dirs);
                this.pathListView.collection.add(data.files);
            }.bind(this));
        }
    });

/*-------------------------------------------------------------
                        UserView
-------------------------------------------------------------*/

    app.UserView = Backbone.View.extend({
        /* View that manages user profile menu. */

        el: '#user-menu-el',

        templates: {
            menu: Handlebars.compile($('#user-menu-template').html())
        },

        initialize: function() {
            this.model = new app.UserModel();
            this.listenTo(this.model, 'change', this.render);
            this.model.fetch();
        },

        render: function() {
            this.$el.html(this.templates.menu(this.model.attributes));
        }
    });

/*-------------------------------------------------------------
                        BreadCrumbView
-------------------------------------------------------------*/

    app.BreadCrumbView = Backbone.View.extend({
        /* View that manages breadcrumb. Renders from a DirectoryModel. */

        el: '#breadcrumb-el',

        templates: {
            breadcrumb: Handlebars.compile($("#breadcrumb-template").html())
        },

        model: new app.DirectoryModel(),

        initialize: function() {
            this.listenTo(this.model, 'change', this.render);
        },

        render: function() {
            var parents = this.model.get('parents');
            parents[0] = 'Home';
            this.$el.html(this.templates.breadcrumb(parents));
        }
    });

/*-------------------------------------------------------------
                        PathMenuView
-------------------------------------------------------------*/

    app.PathMenuView = Backbone.View.extend({
    });

/*-------------------------------------------------------------
                        PathListView
-------------------------------------------------------------*/

    app.PathListView = Backbone.View.extend({
        /* View that manages table of paths. */

        el: '#left-panel-el',

        events: {
            'click #create-button': 'create'
        },

        templates: {
            list: Handlebars.compile($("#path-list-template").html())
        },

        collection: new app.PathCollection(),
        selected: new app.PathCollection(),

        initialize: function() {
            /*
            TODO: customize dropzone so that when a file is dropped on the table
            a new row is added via a new Path model instance. Show progress within
            the table row, and refresh the data after upload (since JSON is returned
            from the API).
            */
            this.$el.dropzone({
                init: function() {
                    this.on("processing", function(file) {
                        // TODO: inject current directory too.
                        this.options.url = "/api/v1/me/files/path:/" + file.name + ":/data/";
                    });
                    // Ensure that when user clicks upload, Dropzone will
                    // "click" the hidden upload file field, allowing the user
                    // to select a file.
                    $('#upload-button').on('click', function() {
                        $(this.hiddenFileInput).trigger('click');
                    }.bind(this));
                },
                // Ask Dropzone to kindly create a hiddenFileInput.
                clickable: true,
                // TODO: Should probably enable uploading to a directory in the API.
                url: "/api/v1/me/files/path:/foobar:/data/",
                headers: {"X-CSRFToken": Cookies.get("csrftoken")}
            });
            this.listenTo(this.collection, 'change', this.render);
            this.listenTo(this.collection, 'add', this.render);
            this.listenTo(this.collection, 'remove', this.render);
            this.listenTo(this.collection, 'select:some', this.selection);
        },

        selection: function(diff, options) {
            this.selected.add(diff.selected);
            this.selected.remove(diff.deselected);
        },

        render: function() {
            this.$el.html(this.templates.list());
            this.collection.forEach(function(item) {
                var pathView = new app.PathItemView({ model: item });
                this.$('tbody').append(pathView.render().$el);
            }.bind(this));
        },

        create: function() {
            new app.CreateView({collection: this.collection});
        }
    });

/*-------------------------------------------------------------
                        PathItemView
-------------------------------------------------------------*/

    app.PathItemView = Backbone.View.extend({
        /* For for an individual path. */

        tagName: 'tr',

        events: {
            'click': 'toggleSelect'
        },

        templates: {
            item: Handlebars.compile($("#path-item-template").html())
        },

        initialize: function() {
            this.listenTo(this.model, 'select', this.onSelect);
            this.listenTo(this.model, 'deselect', this.onDeselect);
        },

        toggleSelect: function() {
            this.model.toggleSelected();
            if (this.model.selected) {
                this.$el.addClass('selected');
            } else {
                this.$el.removeClass('selected');
            }
        },

        render: function() {
            this.$el.html(this.templates.item(this.model.attributes));
            return this;
        }
    });

/*-------------------------------------------------------------
                        CreateView
-------------------------------------------------------------*/

    app.CreateView = Backbone.View.extend({
        /* View that manages create directory dialog. */

        tagName: 'div',
        attributes: {
            'class': "modal fade",
            'role': "dialog"
        },

        events: {
            "click #create-save-button": "save"
        },

        templates: {
            create: Handlebars.compile($("#create-modal-template").html())
        },

        initialize: function() {
            this.render();
        },

        render: function() {
            this.$el.html(this.templates.create()).modal('show');
            this.$el.one('shown.bs.modal', function() {
                this.$('#create-name-input').focus();
            }.bind(this));
        },

        save: function() {
            var name = $('#create-name-input').val();
            $.post('/api/v1/me/dirs/path:/' + name + ':', function(data) {
                var model = new app.DirectoryModel(data);
                this.collection.add(model);
                this.close();
            }.bind(this));
        },

        close: function() {
            this.$el.modal('hide');
            this.remove();
        }
    });

/*==============================================================
             ______            _                
            | ___ \          | |               
            | |_/ /___  _   _| |_ ___ _ __ ___ 
            |    // _ \| | | | __/ _ \ '__/ __|
            | |\ \ (_) | |_| | ||  __/ |  \__ \
            \_| \_\___/ \__,_|\__\___|_|  |___/
                                               
================================================================*/

    app.AppRouter = Backbone.Router.extend({
        routes: {
            '': 'index',
            'files*path': 'files'
        },

        index: function() {
            this.navigate('files/', {trigger: true});
        },

        files: function(path) {
            app.view.files(path);
        }
    });

})(jQuery);

// Initialize our tools.

// register some helpers with handlebars.
Handlebars.registerHelper('fileSize', function(value) {
    if (typeof value === 'undefined') {
        return 'N/A';
    }
    return filesize(value);
});
Handlebars.registerHelper('timeAgo', function(value) {
    return timeago().format(value);
});

// handle CSRF token when doing ajax.
$.ajaxSetup({
    beforeSend: function(xhr, settings) {
        if (!(/^(GET|HEAD|OPTIONS|TRACE)$/.test(settings.type)) && !this.crossDomain) {
            xhr.setRequestHeader("X-CSRFToken", Cookies.get('csrftoken'));
        }
    }
});

// Start our application.
window.onload = function() {
    app.router = new app.AppRouter();
    app.view = new app.AppView();
    Backbone.history.start();
}