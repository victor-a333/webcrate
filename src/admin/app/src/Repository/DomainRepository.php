<?php

namespace App\Repository;

use App\Entity\Project;
use App\Entity\Redirect;
use Doctrine\Bundle\DoctrineBundle\Repository\ServiceEntityRepository;
use Doctrine\Persistence\ManagerRegistry;

class DomainRepository extends ServiceEntityRepository
{
    private $projectRepository;
    private $redirectRepository;

    public function __construct(ManagerRegistry $registry, $projectRepository, $redirectRepository)
    {
        parent::__construct($registry, Project::class);
        $this->projectRepository = $projectRepository;
        $this->redirectRepository = $redirectRepository;
    }

    public function getListForTable(): array
    {
        $list = [];
        
        // Get domains from Projects
        $projects = $this->projectRepository->findAll();
        foreach ($projects as $project) {
            $domains = $project->getDomains();
            if (!empty($domains)) {
                foreach ($domains as $domain) {
                    $list[] = [
                        'domain' => $domain,
                        'type' => 'Project',
                        'name' => $project->getName(),
                        'active' => $project->getActive(),
                        'project_uid' => $project->getUid()
                    ];
                }
            }
        }
        
        // Get domains from Redirects
        $redirects = $this->redirectRepository->findAll();
        foreach ($redirects as $redirect) {
            $domains = $redirect->getDomains();
            if (!empty($domains)) {
                foreach ($domains as $domain) {
                    $list[] = [
                        'domain' => $domain,
                        'type' => 'Redirect',
                        'name' => $redirect->getName(),
                        'active' => $redirect->getActive()
                    ];
                }
            }
        }
        
        return $list;
    }
}
