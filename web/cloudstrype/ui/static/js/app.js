var app = app || {};

(function($) {

    app.AppView = Backbone.View.extend({
        //el: '#main-el',

        initialize: function() {
            this.user = new app.UserView();
            this.paths = new app.PathView();
        },

        render: function() {
            
        }
    });

    app.UserView = Backbone.View.extend({
        el: '#user-menu-el',

        templates: {
            menu: Handlebars.compile($('#user-menu-template').html())
        },

        initialize: function() {
            this.model = new app.UserModel();
            this.listenTo(this.model, 'sync', this.render);
            this.model.fetch();
        },

        render: function() {
            this.$el.html(this.templates.menu(this.model.toJSON()));
        }
    });

    app.UserModel = Backbone.Model.extend({
        url: '/api/v1/me/',
    });

    app.BreadCrumbView = Backbone.View.extend({
    });

    app.BreadCrumbModel = Backbone.Model.extend({
        defauls: {
            path: []
        }
    });

    app.PathView = Backbone.View.extend({
        el: '#main-el',

        // Current browsing location.
        path: '/',

        templates: {
            list: Handlebars.compile($("#path-list-template").html())
        },

        initialize: function() {
            this.collection = new app.PathCollection();
            this.listenTo(this.collection, 'sync', this.render);
            /*
            Here we probably need to do our ajax by ourself and feed the
            data into the PathCollection and BreadCrumb model, since the
            data comes from the server combined, we want to avoid two calls.
            */
            this.collection.fetch();
        },

        render: function() {
            this.$el.html(this.templates.list(this.collection.toJSON()));
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
                },
                // TODO: Should probably enable uploading to a directory in the API.
                url: "/api/v1/me/files/path:/foobar:/data/",
                headers: {"X-CSRFToken": Cookies.get("csrftoken")}
            });
        }
    });

    app.Path = Backbone.Model.extend({
        defaults: {
            directory: false,
            name: null,
            path: null,
            size: null,
            created: null,
            tags: [],
            attrs: {}
        }
    });

    app.PathCollection = Backbone.Collection.extend({
        model: app.Path,

        // TODO: use current directory.
        url: '/api/v1/me/dirs/path:/:',

        parse: function(data) {
            /*
            Parse the directory listing. Data comes from the server as an object.

            {
                info: {
                    // information about the directory being retrieved.
                },
                dirs: [
                    {
                        // information about a child directory.
                    },
                ],
                files: [
                    {
                        // information about a child file.
                    },
                ]
            */

            var listing = [];
            // Combine directories and files into a unified listing, but set a
            // directory flag to true for directories and false for files.
            _.each(data.dirs, function(dir) {
                listing.push({
                    directory: true,
                    name: dir.name,
                    path: dir.path,
                    size: null,
                    created: dir.created,
                    tags: dir.tags,
                    attrs: dir.attrs
                });
            });
            _.each(data.files, function(file) {
                listing.push({
                    directory: false,
                    name: file.name,
                    path: file.path,
                    size: file.size,
                    created: file.created,
                    tags: file.tags,
                    attrs: file.attrs
                });
            });
            return listing;
        }
    });

})(jQuery);

// Initialize our tools.

// register some helpers with handlebars.
Handlebars.registerHelper('fileSize', filesize);
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
    new app.AppView();
}