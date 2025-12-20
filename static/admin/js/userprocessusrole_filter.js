(function() {
    'use strict';

    // Attendre que Django admin et jQuery soient chargés
    function initializeScript() {
        var $ = django.jQuery || window.jQuery;

        if (!$) {
            console.error('jQuery not found');
            return;
        }

        console.log('UserProcessusRole filter script initializing...');

        var userSelect = $('#id_user');
        var processusField = $('.field-processus_multiple');
        // Essayer plusieurs sélecteurs pour trouver les checkboxes de processus
        var processusList = $('#id_processus_multiple, ul[id*="processus_multiple"], .field-processus_multiple ul');

        if (userSelect.length === 0) {
            console.log('User select not found - selector: #id_user');
            return;
        }

        console.log('UserProcessusRole filter script loaded successfully');
        console.log('Processus field found:', processusField.length);
        console.log('Processus list found:', processusList.length);

        // Fonction pour charger les processus d'un utilisateur
        function loadProcessus(userId) {
            console.log('loadProcessus called with userId:', userId);
            
            if (!userId) {
                // Désactiver et masquer les checkboxes si aucun utilisateur sélectionné
                processusField.find('input[type="checkbox"]').prop('disabled', true);
                processusField.hide();
                return;
            }

            // Réessayer de trouver les éléments au cas où ils ne seraient pas encore chargés
            var currentProcessusList = $('#id_processus_multiple, ul[id*="processus_multiple"], .field-processus_multiple ul');
            var currentProcessusField = $('.field-processus_multiple');
            
            console.log('Current processus list found:', currentProcessusList.length);
            console.log('Current processus field found:', currentProcessusField.length);
            
            if (currentProcessusList.length === 0) {
                console.log('Processus checkboxes not found yet, retrying in 500ms...');
                setTimeout(function() {
                    loadProcessus(userId);
                }, 500);
                return;
            }

            // Afficher le champ processus
            currentProcessusField.show();

            // Afficher un message de chargement
            var helpText = currentProcessusField.find('.help');
            if (helpText.length === 0) {
                helpText = $('<p class="help"></p>');
                currentProcessusField.append(helpText);
            }
            helpText.text('Chargement des processus...');

            // Désactiver temporairement les checkboxes
            var checkboxes = currentProcessusList.find('input[type="checkbox"]');
            console.log('Found checkboxes:', checkboxes.length);
            checkboxes.prop('disabled', true);

            // Faire la requête AJAX pour charger les processus
            $.ajax({
                url: '/admin/parametre/userprocessusrole/get_processus/',
                data: { user_id: userId },
                dataType: 'json',
                success: function(data) {
                    console.log('Processus reçus:', data);

                    if (data.processus && data.processus.length > 0) {
                        // Récupérer les UUIDs des processus disponibles et normaliser
                        var availableProcessusUuids = data.processus.map(function(p) { 
                            return String(p.uuid).toLowerCase().trim(); 
                        });
                        console.log('Available processus UUIDs:', availableProcessusUuids);
                        
                        // Fonction pour cocher les processus avec retry
                        function checkProcessusBoxes(retryCount) {
                            retryCount = retryCount || 0;
                            var maxRetries = 10;
                            
                            // Réessayer de trouver les checkboxes
                            var currentProcessusList = $('#id_processus_multiple, ul[id*="processus_multiple"], .field-processus_multiple ul');
                            var checkboxes = currentProcessusList.find('input[type="checkbox"]');
                            console.log('Processing checkboxes (attempt ' + (retryCount + 1) + '):', checkboxes.length);
                            
                            if (checkboxes.length === 0 && retryCount < maxRetries) {
                                console.log('No checkboxes found, retrying in 200ms...');
                                setTimeout(function() {
                                    checkProcessusBoxes(retryCount + 1);
                                }, 200);
                                return;
                            }
                            
                            if (checkboxes.length === 0) {
                                console.error('No checkboxes found after ' + maxRetries + ' retries');
                                helpText.text('Erreur: Impossible de trouver les checkboxes de processus.');
                                return;
                            }
                            
                            var checkedCount = 0;
                            // Cocher automatiquement tous les processus déjà attribués à l'utilisateur
                            checkboxes.each(function() {
                                var checkbox = $(this);
                                var processusUuid = String(checkbox.val()).toLowerCase().trim();
                                console.log('Checking checkbox with UUID:', processusUuid);
                                
                                // Comparer les UUIDs (normalisés)
                                var isAvailable = availableProcessusUuids.some(function(uuid) {
                                    return uuid === processusUuid;
                                });
                                
                                if (isAvailable) {
                                    // Activer et afficher le checkbox
                                    checkbox.prop('disabled', false);
                                    checkbox.closest('li').show();
                                    
                                    // Cocher automatiquement les processus déjà attribués
                                    checkbox.prop('checked', true);
                                    checkedCount++;
                                    console.log('Checked processus:', processusUuid);
                                } else {
                                    // Désactiver et masquer le checkbox
                                    checkbox.prop('disabled', true);
                                    checkbox.prop('checked', false);
                                    checkbox.closest('li').hide();
                                }
                            });
                            
                            console.log('Total checked:', checkedCount);
                            helpText.text('Les processus déjà attribués sont automatiquement cochés (' + checkedCount + '). Vous pouvez en sélectionner d\'autres.');
                        }
                        
                        // Commencer à cocher les processus
                        checkProcessusBoxes();

                        // Charger aussi les rôles déjà attribués
                        loadUserRoles(userId);
                    } else {
                        // Aucun processus disponible - masquer tous les checkboxes
                        var currentProcessusList = $('#id_processus_multiple, ul[id*="processus_multiple"], .field-processus_multiple ul');
                        currentProcessusList.find('input[type="checkbox"]').prop('disabled', true).prop('checked', false);
                        currentProcessusList.find('li').hide();
                        helpText.html(
                            'Aucun processus attribué à cet utilisateur. ' +
                            'Veuillez d\'abord attribuer des processus à cet utilisateur dans ' +
                            '<a href="/admin/parametre/userprocessus/add/" target="_blank">Attributions Processus Utilisateurs</a>.'
                        );
                    }
                },
                error: function(xhr, status, error) {
                    console.error('Erreur lors du chargement des processus:', {
                        status: xhr.status,
                        statusText: xhr.statusText,
                        responseText: xhr.responseText,
                        error: error
                    });
                    
                    // Désactiver tous les checkboxes en cas d'erreur
                    var currentProcessusList = $('#id_processus_multiple, ul[id*="processus_multiple"], .field-processus_multiple ul');
                    currentProcessusList.find('input[type="checkbox"]').prop('disabled', true);
                    
                    var helpText = processusField.find('.help');
                    if (helpText.length === 0) {
                        helpText = $('<p class="help"></p>');
                        processusField.append(helpText);
                    }
                    
                    var errorMessage = 'Erreur lors du chargement des processus. Veuillez réessayer.';
                    if (xhr.status === 500) {
                        try {
                            var response = JSON.parse(xhr.responseText);
                            if (response.error) {
                                errorMessage += '<br><small>Détails: ' + response.error + '</small>';
                            }
                        } catch (e) {
                            // Ignorer si la réponse n'est pas du JSON
                        }
                    }
                    helpText.html('<span style="color: red;">' + errorMessage + '</span>');
                }
            });
        }

        // Fonction pour charger les rôles déjà attribués à un utilisateur
        function loadUserRoles(userId) {
            if (!userId) {
                return;
            }

            var rolesList = $('#id_roles');
            if (rolesList.length === 0) {
                return;
            }

            // Faire la requête AJAX pour charger les rôles
            $.ajax({
                url: '/admin/parametre/userprocessusrole/get_user_roles/',
                data: { user_id: userId },
                dataType: 'json',
                success: function(data) {
                    console.log('Rôles reçus:', data);

                    if (data.roles && data.roles.length > 0) {
                        // Récupérer tous les UUIDs des rôles déjà attribués
                        var roleUuids = data.roles.map(function(r) { return r.role_uuid; });
                        
                        // Cocher automatiquement les rôles déjà attribués
                        rolesList.find('input[type="checkbox"]').each(function() {
                            var checkbox = $(this);
                            var roleUuid = checkbox.val();
                            
                            if (roleUuids.indexOf(roleUuid) !== -1) {
                                checkbox.prop('checked', true);
                            }
                        });
                    }
                },
                error: function(xhr, status, error) {
                    console.error('Erreur lors du chargement des rôles:', error);
                    // Ne pas bloquer l'utilisateur si le chargement des rôles échoue
                }
            });
        }

        // Charger les processus quand l'utilisateur change
        userSelect.on('change', function() {
            var userId = $(this).val();
            console.log('Utilisateur sélectionné:', userId);
            // Attendre un peu pour que le DOM soit mis à jour
            setTimeout(function() {
                loadProcessus(userId);
            }, 100);
        });
        
        // Écouter aussi les événements de clic au cas où
        $(document).on('change', '#id_user', function() {
            var userId = $(this).val();
            console.log('User changed via document listener:', userId);
            setTimeout(function() {
                loadProcessus(userId);
            }, 100);
        });

        // Si un utilisateur est déjà sélectionné au chargement de la page, charger ses processus
        if (userSelect.val()) {
            console.log('User already selected on page load:', userSelect.val());
            // Attendre un peu pour que le DOM soit complètement chargé
            setTimeout(function() {
                loadProcessus(userSelect.val());
            }, 500);
        }
    }

    // Appliquer les styles pour les checkboxes de rôles et processus
    function applyCheckboxStyles() {
        var $ = django.jQuery || window.jQuery;
        // Essayer plusieurs sélecteurs possibles pour les rôles et processus
        var checkboxLists = $('#id_roles, #id_processus_multiple, ul[id*="roles"], ul[id*="processus"], .field-roles ul, .field-processus_multiple ul, ul.compact-checkboxes');
        
        if (checkboxLists.length > 0) {
            console.log('Applying styles to checkbox lists:', checkboxLists.length, 'elements found');
            
            checkboxLists.each(function() {
                var $list = $(this);
                $list.css({
                    'list-style': 'none !important',
                    'padding': '8px',
                    'margin': '0',
                    'display': 'grid',
                    'grid-template-columns': 'repeat(auto-fill, minmax(200px, 1fr))',
                    'gap': '2px',
                    'max-height': '300px',
                    'overflow-y': 'auto',
                    'overflow-x': 'hidden',
                    'border': '1px solid #ddd',
                    'border-radius': '4px',
                    'background-color': '#fafafa'
                });
                
                $list.find('li').css({
                    'margin': '0',
                    'padding': '3px 5px',
                    'border-radius': '2px',
                    'font-size': '12px',
                    'line-height': '1.4'
                });
                
                $list.find('label').css({
                    'display': 'flex',
                    'align-items': 'center',
                    'font-size': '12px',
                    'margin': '0',
                    'padding': '1px 0',
                    'white-space': 'nowrap',
                    'overflow': 'hidden',
                    'text-overflow': 'ellipsis',
                    'color': '#000'
                });
                
                $list.find('input[type="checkbox"]').css({
                    'margin-right': '5px',
                    'width': '14px',
                    'height': '14px',
                    'flex-shrink': '0',
                    'cursor': 'pointer'
                });
            });
        } else {
            console.log('Checkbox lists not found, retrying...');
        }
    }

    // Initialiser quand le DOM est prêt
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            initializeScript();
            // Appliquer les styles plusieurs fois pour s'assurer qu'ils sont appliqués
            setTimeout(applyCheckboxStyles, 100);
            setTimeout(applyCheckboxStyles, 500);
            setTimeout(applyCheckboxStyles, 1000);
        });
    } else {
        initializeScript();
        setTimeout(applyCheckboxStyles, 100);
        setTimeout(applyCheckboxStyles, 500);
        setTimeout(applyCheckboxStyles, 1000);
    }
    
    // Réappliquer les styles après les changements AJAX
    var $ = django.jQuery || window.jQuery;
    if ($) {
        $(document).on('change', '#id_user', function() {
            setTimeout(applyCheckboxStyles, 200);
            setTimeout(applyCheckboxStyles, 500);
        });
        
        // Observer les changements dans le DOM pour détecter l'ajout de checkboxes
        var processusObserver = new MutationObserver(function(mutations) {
            // Vérifier si des checkboxes de processus ont été ajoutés
            var checkboxes = $('.field-processus_multiple input[type="checkbox"]');
            if (checkboxes.length > 0 && userSelect.val()) {
                console.log('Processus checkboxes detected in DOM, reloading...');
                setTimeout(function() {
                    loadProcessus(userSelect.val());
                }, 200);
            }
            applyCheckboxStyles();
        });
        
        // Observer quand le DOM est prêt
        setTimeout(function() {
            var targetNode = document.body;
            if (targetNode) {
                processusObserver.observe(targetNode, {
                    childList: true,
                    subtree: true,
                    attributes: false
                });
            }
        }, 1000);
    }
})();
